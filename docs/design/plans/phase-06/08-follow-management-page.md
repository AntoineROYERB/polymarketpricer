# Phase 6 — Dashboard — Follow Management Page

> **Goal**: Manage followed wallets — list, edit config, unfollow, and discover new wallets to follow via recommendations.
> **AI Agent Instructions**: Create `src/app/follow/page.tsx` with a split view: followed wallets list + recommendations.

---

## Route: `/follow`

## API Endpoints Used

| Action | Endpoint |
|--------|----------|
| List followed | `GET /api/v1/follow` |
| Follow | `POST /api/v1/follow/{wallet}` |
| Update | `PATCH /api/v1/follow/{wallet}` |
| Unfollow | `DELETE /api/v1/follow/{wallet}` |
| Recommendations | `GET /api/v1/follow/recommendations` |
| Category recommendations | `GET /api/v1/follow/recommendations/by-category/{category}` |

**All require auth (API key)** — without auth, show "Login to manage follows" with CTA.

---

## Layout

### Split View: "Following" (left/top) + "Recommended" (right/bottom)

#### Following List
| Column | Description |
|--------|-------------|
| Wallet | Truncated address + profile link |
| Label | Custom label (or "—") |
| Auto-Copy | ON/OFF toggle switch |
| Copy Mode | Badge: Fixed / Proportional |
| Copy Value | $X or X% |
| Category Filter | Comma-separated badges or "All" |
| Actions | Edit (pencil icon) / Unfollow (X icon) |

#### Follow Recommendations
| Column | Description |
|--------|-------------|
| Rank | #1, #2, ... |
| Wallet | Address → profile link |
| Follow Score | 0.XX with color gradient |
| Reasons | Text summary (2-3 reasons) |
| Action | "+ Follow" button |

Tab within recommendations: **Global** | **By Category** (with category selector)

### Edit Modal / Slide Panel
When clicking "Edit" on a followed wallet:
```
┌──────────────────────────────────┐
│  Edit Follow Config              │
│                                  │
│  Label: [________________]       │
│                                  │
│  Auto-copy: [ON/OFF]            │
│                                  │
│  Copy mode: [Fixed ▼]           │
│  Copy value: [_______] $ / %    │
│                                  │
│  Category filter:                │
│  [Politics] [Crypto] [Sports] x │
│  [+ Add category]                │
│                                  │
│  [Cancel]  [Save Changes]        │
└──────────────────────────────────┘
```

### Unfollow Confirmation
```tsx
// Dialog: "Unfollow 0x1234...abcd?"
// Warning: "You will stop receiving alerts and auto-copy trades"
// [Cancel] [Unfollow]
```

---

## States

| State | Behaviour |
|-------|-----------|
| Not authenticated | "Login to manage follows" with login CTA |
| Loading | Side-by-side skeleton lists |
| No follows | Empty state: "You're not following anyone yet" + recommendations |
| No recommendations | "No recommendations available" |
| Follow success | Toast notification + list updates |
| Unfollow | Confirmation dialog → remove from list + toast |

---

## Files to Create

| Action | Path |
|--------|------|
| CREATE | `src/app/follow/page.tsx` |

---

## Verification

```bash
curl http://localhost:3000/follow
# Expected: followed wallets list (or empty state)

# Test:
# - List followed wallets with config
# - Edit opens modal with pre-filled values
# - Save changes → PATCH request → list updates
# - Unfollow → confirmation → DELETE → list updates
# - Recommendations tab shows global + by-category
# - Follow button on recommendation → POST → appears in Following list
```
