# RIOT RADAR — Business Logic & Case Calibration

## 1. Case Facts & Source of Truth (Pulp Riot Juice Co.)
- **Annual Revenue:** ₹1,200 crore.
- **Contribution Margin:** 32%.
- **Summer Revenue (March–June):** ₹576 crore (48% of annual revenue).
- **Summer Finished Goods Volume:** ~9.6 crore bottles @ ₹60/bottle retail.
- **Production Capacity:** 2 plants with 2.5 crore bottles/month combined, operating at 95% summer utilization.
- **Co-Packer Reality Check:** Up to 10% additional volume, +25% cost premium, 2 weeks' notice. **Co-packer cannot resolve raw pulp scarcity.**
- **Distribution Network:** 9 regional depots, ~600 GT distributors.
- **Channel Mix:** General Trade (GT) 55%, Modern Trade (MT) 25%, Quick Commerce (QC) 20%.
- **Shelf Life Rules:**
  - Bottled juice: 90 days.
  - MT/QC reject stock with < 60 days remaining.
  - GT accepts stock with < 60 days remaining.
  - Frozen fruit pulp: up to 6 months.
- **Target Inventory Cover:** 21 days across finished goods.
- **Depot Transfers:** 2 to 4 days physical transit, ₹1.50/bottle freight cost.
- **Historical Information Asymmetry:**
  - QC dark-store sell-through available daily (1-day lag), but planners historically receive consolidated dispatches at month-end (30-day lag).
  - Depot stock reported weekly (7-day lag).
  - Historical flavour/depot forecast error: ~30% WAPE.
- **Passionfruit Disruption:**
  - Single-source Northeast plantation route. 3-day road transit with no alternate road.
  - Highway closed for 3 weeks in May; starting plant pulp cover was ~14 days (2 weeks).
  - Emergency air freight incurred: ₹3.20 crore (~5x road cost).
- **Dragonfruit Bloom (PR-DB):** 40% imported dragonfruit pulp on 6–8 week quarterly lead time.
- **Dragon Passion (PR-DP):** Fourfold QC demand spike over 14 days after viral influencer video in March/May. Competes with Passionfruit Punch (PR-PP) for passionfruit pulp.
- **Historical Loss Figures (Separate, Non-Overlapping):**
  - Stock-out Lost Revenue: ₹46.08 crore.
  - Illustrative Foregone Contribution: ₹14.75 crore (32% of ₹46.08 Cr).
  - Overstock Write-offs & Discounts: ₹6.00 crore.
  - Emergency Air Freight: ₹3.20 crore.
  - Bottom-Line Exposure: ₹14.75 Cr + ₹6.00 Cr + ₹3.20 Cr = **₹23.95 crore**.
  - Year-1 System Budget Cap: **₹2.50 crore**, representing an illustrative **10.4% Break-Even Recovery Hurdle**.

---

## 2. The 45 SKU–Depot Operational Grain
5 finished goods SKUs × 9 regional depots = 45 combinations.

### Finished Goods SKUs
1. `PR-MPB`: Mango Peach Basil (38% summer share) — High volume, excess stock and shelf-life cliff.
2. `PR-GC`: Guava Chilli (20% summer share) — Cross-depot imbalance and GT reallocation.
3. `PR-PP`: Passionfruit Punch (16% summer share) — Single-source pulp and highway closure.
4. `PR-DB`: Dragonfruit Bloom (14% summer share) — 40% imported pulp and long lead time.
5. `PR-DP`: Dragon Passion (12% summer share) — Fourfold QC spike and shared passionfruit pulp.

### Depots
`Depot-North-01` (Delhi NCR), `Depot-North-02` (Lucknow), `Depot-West-01` (Mumbai), `Depot-West-02` (Ahmedabad), `Depot-South-01` (Bengaluru), `Depot-South-02` (Chennai), `Depot-East-01` (Kolkata), `Depot-East-02` (Guwahati), `Depot-Central-01` (Indore).

---

## 3. Mathematical Formulas & Conventions
- **Demand Uplift %:**
  $$\text{Demand Uplift \%} = \frac{\text{Corrected Demand} - \text{Observed Demand}}{\text{Observed Demand}} \times 100$$
  *Safe handling:* If observed demand is 0, returns `N/A` (None) to avoid division by zero.
- **Service Level (Estimated Fill Rate %):**
  $$\text{Fill Rate \%} = \min\left(100.0, \frac{\text{Fulfilled Demand}}{\text{Total Estimated Corrected Demand}} \times 100\right)$$
- **Target Stock:**
  $$\text{Target Stock} = \text{Corrected Daily Forecast Demand} \times 21\text{ days}$$
- **Allocation Gap:**
  $$\text{Allocation Gap} = \text{Target Stock} - \text{Projected Usable Inventory}$$
- **Days of Cover (DoC):**
  $$\text{DoC} = \frac{\text{Total Usable Inventory}}{\text{Corrected Daily Forecast Demand}}$$
  *Safe handling:* If daily demand is 0 and inventory > 0, returns `None` (disclosed infinite cover convention).
- **67-Day Near-Cliff Threshold:**
  $$60\text{d MT/QC Rejection} + 4\text{d Max Transit} + 1\text{d Approval Latency} + 2\text{d Safety Buffer} = 67\text{ days}$$
- **Effective Transfer ETA:**
  $$\text{Effective ETA} = \text{Physical Transit (2–4d)} + 1\text{d Approval Latency} = 3\text{ to }5\text{ days}$$
- **Transfer Cost:**
  $$\text{Transfer Cost} = \text{Transfer Quantity (Bottles)} \times ₹1.50$$
