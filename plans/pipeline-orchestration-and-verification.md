# Pipeline Orchestration & Post-Run Verification

## Objectif

Configurer Mage triggers pour exécuter les 6 pipelines ETL en **moins de 5 minutes**, avec une **étape de vérification** finale qui valide le remplissage de toutes les colonnes critiques.

---

## 1. Conventions de nommage

### Global variables (dans `magic/default_repo/__init__.py`)

```python
# Seuils de vérification post-run
POLYMARKET_MIN_MARKETS    = 50000
POLYMARKET_MIN_OUTCOMES   = 100000
POLYMARKET_MIN_WALLETS    = 1000
POLYMARKET_MIN_POSITIONS  = 5000
POLYMARKET_MIN_TRADES     = 50000
POLYMARKET_MIN_ANALYTICS  = 500
POLYMARKET_MIN_RANKINGS   = 100

# Filtres ranking
POLYMARKET_MIN_TRADES_FOR_RANKING = 50
POLYMARKET_MIN_VOLUME_FOR_RANKING = 1000

# Timeouts (secondes)
POLYMARKET_TIMEOUT_MARKET_DISCOVERY  = 120
POLYMARKET_TIMEOUT_WALLET_DISCOVERY  = 120
POLYMARKET_TIMEOUT_POSITION_SYNC     = 120
POLYMARKET_TIMEOUT_TRADE_HISTORY     = 120
POLYMARKET_TIMEOUT_ANALYTICS         = 60
POLYMARKET_TIMEOUT_RANKING           = 30

# SLA global
POLYMARKET_TOTAL_SLA_SECONDS = 300  # 5 min
```

Ces variables sont placées dans `magic/default_repo/__init__.py` et accessibles via `kwargs['context']['variables']` dans les blocs, ou utilisées directement depuis les scripts Python qui chargent `default_repo`.

### Trigger names

| Trigger pattern | Exemple |
|---|---|
| `POLYMARKET_TRIGGER_{PIPELINE}_SCHEDULE` | `POLYMARKET_TRIGGER_MARKET_DISCOVERY_SCHEDULE` |
| `POLYMARKET_TRIGGER_ORCHESTRATOR` | `POLYMARKET_TRIGGER_ORCHESTRATOR` |

### Pipeline runtime variables (paramètres passés au trigger)

| Variable | Type | Default | Description |
|---|---|---|---|
| `run_date` | string (ISO date) | `today` | Date cible du snapshot |
| `backfill_days` | int | `1` | Fenêtre de reprise en jours |
| `min_trades` | int | `50` | Seuil trades pour ranking eligibility |
| `min_volume` | int | `1000` | Seuil volume pour ranking eligibility |

---

## 2. Dépendances entre pipelines

```
market_discovery
    │
    ▼
wallet_discovery
    │
    ├──► position_sync  ──┐
    │                      │
    └──► trade_history  ──┤
                           ▼
                   analytics_computation
                           │
                           ▼
                   ranking_computation
                           │
                           ▼
                   verification (block final)
```

### Parallélisation possible

- `position_sync` et `trade_history` peuvent tourner **en parallèle** après `wallet_discovery`.
- `load_active_markets` et `load_resolved_markets` (dans `market_discovery`) tournent déjà en parallèle dans le même pipeline.

---

## 3. Configuration des triggers

Chaque pipeline reçoit un trigger YAML dans `magic/default_repo/pipelines/{uuid}/triggers/`.

### 3.1 Trigger pour `market_discovery`

**Fichier :** `magic/default_repo/pipelines/market_discovery/triggers/default.yaml`

```yaml
name: POLYMARKET_TRIGGER_MARKET_DISCOVERY_SCHEDULE
pipeline_uuid: market_discovery
schedule_interval: "@daily"
schedule_type: time
start_time: "2026-06-17T00:00:00"
status: active

variables:
  run_date: "{{ execution_date }}"
  backfill_days: 1

settings:
  sla: 120
  allow_parallel_runs: false
  landing_time_enabled: true
  landing_time_interval: 300

runtime_parameters:
  - name: run_date
    type: string
    required: true
    default: "{{ execution_date }}"
  - name: backfill_days
    type: int
    required: false
    default: 1
```

### 3.2 Trigger pour `wallet_discovery`

**Fichier :** `magic/default_repo/pipelines/wallet_discovery/triggers/default.yaml`

```yaml
name: POLYMARKET_TRIGGER_WALLET_DISCOVERY_SCHEDULE
pipeline_uuid: wallet_discovery
schedule_interval: null           # pas de schedule autonome, chainé
schedule_type: api
status: active

variables:
  run_date: "{{ execution_date }}"

settings:
  sla: 120
  allow_parallel_runs: false
```

### 3.3 Trigger pour `position_sync`

**Fichier :** `magic/default_repo/pipelines/position_sync/triggers/default.yaml`

```yaml
name: POLYMARKET_TRIGGER_POSITION_SYNC_SCHEDULE
pipeline_uuid: position_sync
schedule_interval: null
schedule_type: api
status: active

variables:
  run_date: "{{ execution_date }}"

settings:
  sla: 120
```

### 3.4 Trigger pour `trade_history`

**Fichier :** `magic/default_repo/pipelines/trade_history/triggers/default.yaml`

```yaml
name: POLYMARKET_TRIGGER_TRADE_HISTORY_SCHEDULE
pipeline_uuid: trade_history
schedule_interval: null
schedule_type: api
status: active

variables:
  run_date: "{{ execution_date }}"

settings:
  sla: 120
```

### 3.5 Trigger pour `analytics_computation`

**Fichier :** `magic/default_repo/pipelines/analytics_computation/triggers/default.yaml`

```yaml
name: POLYMARKET_TRIGGER_ANALYTICS_SCHEDULE
pipeline_uuid: analytics_computation
schedule_interval: null
schedule_type: api
status: active

variables:
  run_date: "{{ execution_date }}"

settings:
  sla: 60
```

### 3.6 Trigger pour `ranking_computation`

**Fichier :** `magic/default_repo/pipelines/ranking_computation/triggers/default.yaml`

```yaml
name: POLYMARKET_TRIGGER_RANKING_SCHEDULE
pipeline_uuid: ranking_computation
schedule_interval: null
schedule_type: api
status: active

variables:
  run_date: "{{ execution_date }}"
  min_trades: "{{ global_var('POLYMARKET_MIN_TRADES_FOR_RANKING') }}"
  min_volume: "{{ global_var('POLYMARKET_MIN_VOLUME_FOR_RANKING') }}"

settings:
  sla: 30
```

---

## 4. Pipeline orchestrator (chainé)

### Option A — Backend script (recommandé pour le contrôle)

Utiliser `scripts/run_all.py` existant, enrichi avec parallélisation et gestion de timeouts :

```python
"""Orchestrateur ETL avec parallélisation et timeouts SLA."""

import sys
import time
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed

sys.path.insert(0, "/home/src/default_repo")

SLA_TOTAL = 300  # 5 minutes


def run_in_thread(fn, name, timeout):
    """Execute une pipeline dans un thread avec timeout."""
    future = executor.submit(fn)
    try:
        future.result(timeout=timeout)
        return name, True, None
    except Exception as e:
        return name, False, str(e)


def run_all():
    t_start = time.time()

    # Phase 1: market_discovery (seul)
    run_market_discovery()
    elapsed = time.time() - t_start
    print(f"[{elapsed:.0f}s] Phase 1: market_discovery done")

    # Phase 2: wallet_discovery (seul)
    run_wallet_discovery()
    elapsed = time.time() - t_start
    print(f"[{elapsed:.0f}s] Phase 2: wallet_discovery done")

    # Phase 3: position_sync + trade_history en parallèle
    with ThreadPoolExecutor(max_workers=2) as pool:
        fut_pos = pool.submit(run_position_sync)
        fut_trd = pool.submit(run_trade_history)
        for fut in as_completed([fut_pos, fut_trd]):
            fut.result()  # propagate exceptions
    elapsed = time.time() - t_start
    print(f"[{elapsed:.0f}s] Phase 3: position_sync + trade_history done")

    # Phase 4: analytics_computation (dépend des deux précédents)
    run_analytics()
    elapsed = time.time() - t_start
    print(f"[{elapsed:.0f}s] Phase 4: analytics done")

    # Phase 5: ranking (dépend des analytics)
    run_ranking()
    elapsed = time.time() - t_start
    print(f"[{elapsed:.0f}s] Phase 5: ranking done")

    # Vérification SLA global
    total = time.time() - t_start
    if total > SLA_TOTAL:
        print(f"⚠ SLA dépassé: {total:.0f}s > {SLA_TOTAL}s")
        sys.exit(1)
    print(f"✓ Cycle ETL terminé en {total:.0f}s")
```

### Option B — Mage Event Trigger (pour l'automatisation native)

Créer un trigger "event" qui écoute la complétion de chaque pipeline et enchaîne le suivant :

```yaml
# magic/default_repo/triggers/etl_orchestrator.yaml
name: POLYMARKET_TRIGGER_ORCHESTRATOR
schedule_type: api
status: active

triggers:
  - pipeline_uuid: market_discovery
    on_success:
      - pipeline_uuid: wallet_discovery
  - pipeline_uuid: wallet_discovery
    on_success:
      - pipeline_uuid: position_sync
      - pipeline_uuid: trade_history
  - pipeline_uuid: position_sync
    on_success:
      - pipeline_uuid: analytics_computation
  - pipeline_uuid: trade_history
    on_success:
      - pipeline_uuid: analytics_computation
  - pipeline_uuid: analytics_computation
    on_success:
      - pipeline_uuid: ranking_computation
  - pipeline_uuid: ranking_computation
    on_success:
      - pipeline_uuid: verify_etl_output   # bloc ou pipeline de vérification
```

---

## 5. Bloc de vérification post-run

### 5.1 Data loader de vérification

**Fichier :** `magic/default_repo/data_loaders/verify_etl_output.py`

```python
"""Vérifie que toutes les tables sont correctement remplies après le run ETL."""

from datetime import date, datetime, timezone
from pandas import DataFrame, read_sql
from sqlalchemy import create_engine, text

DATABASE_URL = "postgresql://app:devpassword@postgres:5432/polymarket"

# Seuils (peuvent être surchargés via runtime variables)
DEFAULT_THRESHOLDS = {
    "markets": 50000,
    "outcomes": 100000,
    "wallets": 1000,
    "positions": 5000,
    "trades": 50000,
    "wallet_analytics": 500,
    "ranking_snapshots": 100,
}

REQUIRED_COLUMNS = {
    "markets": ["id", "question"],
    "outcomes": ["id", "market_id", "label"],
    "wallets": ["wallet"],
    "positions": ["wallet", "market_id", "status"],
    "trades": ["id", "wallet", "market_id", "side", "price", "shares", "amount_usd", "timestamp"],
    "wallet_analytics": [
        "wallet", "snapshot_date", "total_pnl", "roi", "num_trades",
        "consistency_score", "experience_score", "wallet_score",
    ],
    "ranking_snapshots": [
        "wallet", "snapshot_date", "list_type", "rank", "wallet_score",
    ],
}


@data_loader
def load_data_from_api(*args, **kwargs) -> DataFrame:
    context = kwargs.get("context", {})
    variables = context.get("variables", {})
    thresholds = {
        tbl: variables.get(f"min_{tbl}", default)
        for tbl, default in DEFAULT_THRESHOLDS.items()
    }

    engine = create_engine(DATABASE_URL)
    errors = []

    # 1. Vérifier les row counts
    print("=== Vérification des row counts ===")
    for tbl, min_rows in thresholds.items():
        count = engine.execute(text(f"SELECT count(*) FROM {tbl}")).scalar()
        if count < min_rows:
            errors.append(f"{tbl}: {count} lignes, attendu >= {min_rows}")
        else:
            print(f"  ✓ {tbl}: {count} lignes")

    # 2. Vérifier les NOT NULL sur colonnes critiques
    print("=== Vérification NOT NULL ===")
    for tbl, cols in REQUIRED_COLUMNS.items():
        for col in cols:
            nulls = engine.execute(
                text(f"SELECT count(*) FROM {tbl} WHERE {col} IS NULL")
            ).scalar()
            if nulls > 0:
                errors.append(f"{tbl}.{col}: {nulls} NULLs")

    # 3. Vérifier l'intégrité référentielle
    print("=== Vérification FK ===")
    fk_checks = [
        ("positions", "wallets", "wallet", "wallet"),
        ("positions", "markets", "market_id", "id"),
        ("trades", "wallets", "wallet", "wallet"),
        ("trades", "markets", "market_id", "id"),
        ("wallet_analytics", "wallets", "wallet", "wallet"),
        ("ranking_snapshots", "wallets", "wallet", "wallet"),
    ]
    for child, parent, c_col, p_col in fk_checks:
        orphans = engine.execute(
            text(
                f"SELECT count(*) FROM {child} c "
                f"LEFT JOIN {parent} p ON c.{c_col} = p.{p_col} "
                f"WHERE p.{p_col} IS NULL"
            )
        ).scalar()
        if orphans > 0:
            errors.append(f"FK {child}.{c_col} → {parent}.{p_col}: {orphans} orphelins")

    # 4. Qualité wallet_analytics
    print("=== Vérification qualité analytics ===")
    quality_checks = [
        ("total_pnl > 100000 OR total_pnl < -100000", "PNL hors ±100k"),
        ("win_rate IS NOT NULL AND (win_rate < 0 OR win_rate > 1)", "win_rate hors [0,1]"),
        ("wallet_score IS NOT NULL AND (wallet_score < 0 OR wallet_score > 100)", "wallet_score hors [0,100]"),
        ("max_drawdown IS NOT NULL AND max_drawdown > 0", "max_drawdown > 0"),
        ("profit_factor IS NOT NULL AND profit_factor < 0", "profit_factor < 0"),
        ("consistency_score IS NULL", "consistency_score NULL"),
        ("experience_score IS NULL", "experience_score NULL"),
    ]
    for condition, label in quality_checks:
        bad = engine.execute(
            text(f"SELECT count(*) FROM wallet_analytics WHERE {condition}")
        ).scalar()
        if bad > 0:
            errors.append(f"wallet_analytics: {label} ({bad} rows)")

    # 5. Timestamps futurs
    print("=== Vérification timestamps ===")
    now = datetime.now(timezone.utc)
    future_trades = engine.execute(
        text("SELECT count(*) FROM trades WHERE timestamp > :now"),
        {"now": now},
    ).scalar()
    if future_trades > 0:
        errors.append(f"trades: {future_trades} timestamps futurs")

    # 6. Ranking diversity (top_100, emerging, consistent)
    print("=== Vérification rankings ===")
    list_types = engine.execute(
        text("SELECT list_type, count(*) FROM ranking_snapshots GROUP BY list_type")
    ).all()
    found_types = {row[0]: row[1] for row in list_types}
    for lt in ["top_100", "emerging", "consistent"]:
        count = found_types.get(lt, 0)
        print(f"  {lt}: {count}")

    engine.dispose()

    # Résultat
    if errors:
        error_msg = "\n".join(errors)
        raise RuntimeError(f"Vérification ETL échouée:\n{error_msg}")
    else:
        print("\n=== ✓ VÉRIFICATION ETL PASSÉE ===")
```

### 5.2 Intégration dans la CI

Ajouté comme un bloc `data_loader` dans la pipeline `ranking_computation` (dernière étape), ou comme pipeline indépendante déclenchée par le succès du ranking.

---

## 6. Estimateur de temps (cible < 5 min)

| Phase | Pipelines | Mode | Est. temps |
|---|---|---|---|
| 1 | `market_discovery` | Séquentiel | ~45s |
| 2 | `wallet_discovery` | Séquentiel | ~45s |
| 3 | `position_sync` + `trade_history` | Parallèle (max 2 workers) | ~60s |
| 4 | `analytics_computation` | Séquentiel | ~15s |
| 5 | `ranking_computation` + vérification | Séquentiel | ~10s |
| **Total** | | | **~175s (< 3 min)** |

Marge SLA : 300s → confortable.

---

## 7. Implémentation

### Étapes

1. Créer `magic/default_repo/__init__.py` avec les global variables
2. Créer les dossiers `triggers/` pour chaque pipeline
3. Créer les fichiers YAML de trigger (6 fichiers)
4. Créer `magic/default_repo/data_loaders/verify_etl_output.py`
5. Option A : enrichir `scripts/run_all.py` avec parallélisation et timeouts
6. Option B : créer le trigger orchestrator `magic/default_repo/triggers/etl_orchestrator.yaml`
7. Tester le cycle complet : `docker compose exec mage python scripts/run_all.py`
8. Vérifier le temps total et ajuster les SLA si nécessaire
