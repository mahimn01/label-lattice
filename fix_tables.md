### Before / after: falsifier metric (5 seeds, mean [min-max])

**few_large**

| scenario | BEFORE artifact mass <=3 principals | before | LMF component mass <=3 | LMF cost-weighted unshareable (rho .15) | LMF verdict | arm B cover mass <=3 | arm B |
|---|---|---|---|---|---|---|---|
| few_large/priv00 | 21.0% [20.1-22.8] | PASS | 1.2% [0.8-2.4] | 4.5% [3.9-5.2] | PASS | 71.9% [65.7-75.8] | FAIL |
| few_large/priv05 | 28.6% [26.0-32.3] | PASS | 4.1% [3.1-5.3] | 7.8% [6.1-9.8] | PASS | 68.9% [58.0-75.6] | FAIL |
| few_large/priv10 | 33.0% [29.5-37.7] | PASS | 7.1% [5.2-8.9] | 11.0% [8.6-12.5] | PASS | 70.4% [65.6-77.7] | FAIL |
| few_large/priv20 | 42.2% [37.6-52.2] | MIXED (4/5) | 13.3% [10.5-15.3] | 17.1% [14.7-19.8] | PASS | 77.3% [68.6-86.6] | FAIL |
| few_large/priv30 | 56.6% [54.4-62.6] | FAIL | 19.7% [16.1-22.8] | 24.8% [21.8-27.2] | PASS | 84.3% [79.4-88.0] | FAIL |
| few_large/priv40 | 63.2% [50.1-71.5] | FAIL | 28.4% [24.3-31.5] | 33.1% [28.1-36.7] | PASS | 87.0% [78.6-91.6] | FAIL |
| few_large/priv50 | 66.4% [59.5-78.5] | FAIL | 36.2% [30.9-45.1] | 40.1% [35.2-49.0] | PASS | 91.0% [85.4-94.5] | FAIL |
| few_large/priv60 | 80.3% [73.8-86.6] | FAIL | 49.9% [35.8-57.2] | 53.9% [41.1-60.5] | MIXED (1/5) | 91.4% [82.8-95.9] | FAIL |

**medium**

| scenario | BEFORE artifact mass <=3 principals | before | LMF component mass <=3 | LMF cost-weighted unshareable (rho .15) | LMF verdict | arm B cover mass <=3 | arm B |
|---|---|---|---|---|---|---|---|
| medium/priv00 | 29.4% [26.5-34.0] | PASS | 1.8% [1.2-2.9] | 6.4% [5.2-7.7] | PASS | 60.7% [58.3-65.8] | FAIL |
| medium/priv05 | 40.8% [33.6-49.6] | PASS | 4.5% [3.7-6.7] | 10.3% [8.5-12.7] | PASS | 68.0% [56.1-72.6] | FAIL |
| medium/priv10 | 45.0% [37.5-55.6] | MIXED (4/5) | 9.1% [7.9-10.3] | 14.3% [12.5-16.0] | PASS | 71.6% [64.1-76.6] | FAIL |
| medium/priv20 | 50.2% [45.3-54.0] | MIXED (2/5) | 14.7% [12.3-19.2] | 19.9% [18.0-24.4] | PASS | 78.6% [72.8-84.6] | FAIL |
| medium/priv30 | 59.3% [51.8-63.5] | FAIL | 21.9% [20.0-25.6] | 27.5% [25.5-30.9] | PASS | 75.7% [65.5-82.2] | FAIL |
| medium/priv40 | 66.9% [61.4-71.3] | FAIL | 32.8% [26.2-37.1] | 37.7% [31.6-42.0] | PASS | 82.4% [76.4-89.3] | FAIL |
| medium/priv50 | 78.7% [73.0-83.1] | FAIL | 45.7% [36.5-53.2] | 50.3% [41.8-57.4] | MIXED (3/5) | 88.4% [82.6-92.3] | FAIL |
| medium/priv60 | 81.3% [72.6-84.6] | FAIL | 50.9% [43.1-54.7] | 55.1% [46.6-58.8] | MIXED (1/5) | 88.0% [80.6-91.1] | FAIL |

**many_small**

| scenario | BEFORE artifact mass <=3 principals | before | LMF component mass <=3 | LMF cost-weighted unshareable (rho .15) | LMF verdict | arm B cover mass <=3 | arm B |
|---|---|---|---|---|---|---|---|
| many_small/priv00 | 38.6% [32.3-47.1] | PASS | 3.9% [2.7-5.3] | 9.4% [7.2-11.9] | PASS | 57.6% [47.6-65.1] | MIXED (1/5) |
| many_small/priv05 | 43.4% [36.5-49.2] | PASS | 7.0% [5.5-7.7] | 12.9% [12.0-13.5] | PASS | 66.0% [61.5-69.3] | FAIL |
| many_small/priv10 | 50.9% [42.2-61.1] | MIXED (2/5) | 12.0% [8.2-20.3] | 18.1% [13.4-26.1] | PASS | 68.7% [58.8-77.6] | FAIL |
| many_small/priv20 | 65.7% [62.2-70.0] | FAIL | 19.4% [14.1-24.1] | 26.0% [21.5-30.7] | PASS | 79.3% [75.1-83.2] | FAIL |
| many_small/priv30 | 60.1% [53.1-64.1] | FAIL | 23.3% [17.7-27.3] | 28.9% [25.0-33.0] | PASS | 76.8% [68.8-82.9] | FAIL |
| many_small/priv40 | 70.7% [61.0-76.2] | FAIL | 32.2% [26.5-38.4] | 38.0% [33.1-43.3] | PASS | 80.3% [71.5-85.1] | FAIL |
| many_small/priv50 | 76.2% [64.2-84.8] | FAIL | 45.1% [34.5-56.0] | 49.8% [40.6-59.6] | MIXED (2/5) | 83.9% [77.2-87.9] | FAIL |
| many_small/priv60 | 86.5% [83.1-88.6] | FAIL | 59.1% [52.2-63.3] | 63.0% [57.3-66.5] | FAIL | 91.9% [89.9-95.4] | FAIL |

**Sensitivity and combos (medium unless named)**

| scenario | BEFORE artifact mass <=3 principals | before | LMF component mass <=3 | LMF cost-weighted unshareable (rho .15) | LMF verdict | arm B cover mass <=3 | arm B |
|---|---|---|---|---|---|---|---|
| sens/adhoc_frac=0.15 | 54.0% [52.1-56.4] | FAIL | 8.6% [7.6-11.4] | 15.6% [14.5-17.6] | PASS | 75.8% [67.9-82.2] | FAIL |
| sens/small_frac=0.5 | 47.1% [39.3-51.6] | MIXED (3/5) | 6.1% [4.5-7.7] | 12.4% [11.0-14.1] | PASS | 75.4% [71.5-81.1] | FAIL |
| sens/priv20_pop_mult=4.0 | 75.5% [62.5-84.1] | FAIL | 39.1% [30.8-45.5] | 43.8% [34.7-49.6] | PASS | 86.9% [82.3-91.9] | FAIL |
| sens/priv50_pop_mult=0.25 | 55.1% [48.9-63.7] | MIXED (1/5) | 17.7% [11.0-26.2] | 23.8% [17.8-31.8] | PASS | 72.6% [66.0-79.7] | FAIL |
| sens/art_mode=random | 25.8% [15.3-38.6] | PASS | 1.3% [0.5-2.5] | 4.7% [2.4-7.7] | PASS | 74.4% [52.1-86.0] | FAIL |
| sens/doc_zipf=0.7 | 53.8% [49.1-59.8] | MIXED (2/5) | 6.2% [4.3-11.3] | 13.3% [11.4-18.4] | PASS | 79.1% [74.3-83.0] | FAIL |
| mixed/priv15_adhoc10_med | 54.2% [50.6-57.3] | FAIL | 14.8% [11.3-17.7] | 20.9% [17.0-23.5] | PASS | 75.3% [69.7-84.7] | FAIL |
| combo/worst_case | 65.5% [58.1-68.1] | FAIL | 24.9% [21.4-28.7] | 31.3% [28.6-34.6] | PASS | 78.0% [71.3-85.1] | FAIL |
| combo/best_case | 9.7% [6.9-11.5] | PASS | 0.0% [0.0-0.0] | 1.7% [1.2-2.1] | PASS | 53.1% [42.0-61.4] | MIXED (1/5) |

### Hit rate, storage and compute (rho = 0.15)

| scenario | per-user artifact hit rate | old shared artifact hit rate | LMF component hit rate (shared) | entries per-user | entries LMF (comp+composite) | entries LMF (admit composite on 2nd read) | storage units LMF / per-user | compute LMF / per-user | compute LMF / old shared lattice | break-even rho |
|---|---|---|---|---|---|---|---|---|---|---|
| medium/priv05 | 74.4% [73.0-76.2] | 91.9% [91.9-91.9] | 98.0% [97.9-98.1] | 255,693 | 141,983 | 117,513 | 0.14 | 0.14 | 0.39 | >=15.54 |
| medium/priv20 | 78.4% [77.6-80.7] | 91.9% [91.9-91.9] | 98.0% [97.8-98.1] | 216,028 | 141,569 | 117,099 | 0.16 | 0.16 | 0.41 | >=3.45 |
| medium/priv30 | 80.6% [79.0-82.0] | 91.9% [91.9-91.9] | 97.8% [97.7-97.9] | 193,702 | 141,179 | 116,709 | 0.19 | 0.19 | 0.42 | 1.50-2.47 |
| medium/priv50 | 85.2% [83.4-87.1] | 91.9% [91.9-91.9] | 97.7% [97.4-97.8] | 148,046 | 141,047 | 116,577 | 0.26 | 0.26 | 0.45 | >=0.22 |
| few_large/priv30 | 77.4% [75.6-79.2] | 91.9% [91.9-91.9] | 97.9% [97.8-98.2] | 226,085 | 141,419 | 116,948 | 0.15 | 0.15 | 0.41 | 2.73-4.49 |
| many_small/priv30 | 82.6% [82.0-84.2] | 91.9% [91.9-91.9] | 97.8% [97.6-98.0] | 173,767 | 141,047 | 116,577 | 0.22 | 0.22 | 0.43 | 1.11-5.04 |
| sens/adhoc_frac=0.15 | 78.7% [77.3-80.1] | 91.9% [91.9-91.9] | 98.0% [97.9-98.1] | 212,563 | 141,782 | 117,312 | 0.17 | 0.17 | 0.40 | 2.76-4.25 |
| combo/worst_case | 83.1% [81.6-84.5] | 91.9% [91.9-91.9] | 97.6% [97.4-97.8] | 168,660 | 141,240 | 116,769 | 0.23 | 0.23 | 0.43 | 0.89-1.41 |
| combo/best_case | 61.1% [59.9-62.2] | 91.9% [91.9-91.9] | 98.2% [98.1-98.3] | 388,682 | 142,100 | 117,629 | 0.08 | 0.08 | 0.37 | never (join alone <50%) |
| sens/priv20_pop_mult=4.0 | 84.4% [83.4-86.4] | 91.9% [91.9-91.9] | 97.8% [97.7-97.9] | 155,547 | 136,604 | 112,134 | 0.22 | 0.22 | 0.43 | 0.17-1.74 |

### Join cost sweep (cost-weighted unshareable fraction; rho = join cost / chunk work)

| scenario | M2 rho .05 | M2 .15 | M2 .30 | M2 1.0 | compute/per-user .05 | .15 | .30 | 1.0 | compute/old shared .05 | .15 | .30 | 1.0 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| medium/priv05 | 6.6% [5.4-8.9] | 10.3% [8.5-12.7] | 14.7% [12.1-17.3] | 26.5% [22.0-29.8] | 0.10 | 0.14 | 0.19 | 0.43 | 0.29 | 0.39 | 0.54 | 1.24 |
| medium/priv30 | 23.9% [22.0-27.5] | 27.5% [25.5-30.9] | 31.8% [29.8-35.0] | 43.3% [41.2-45.9] | 0.14 | 0.19 | 0.26 | 0.57 | 0.32 | 0.42 | 0.57 | 1.27 |
| many_small/priv30 | 25.3% [20.3-29.4] | 28.9% [25.0-33.0] | 33.2% [28.6-37.3] | 44.8% [38.2-48.9] | 0.17 | 0.22 | 0.29 | 0.65 | 0.33 | 0.43 | 0.58 | 1.28 |
| combo/worst_case | 27.2% [24.0-30.9] | 31.3% [28.6-34.6] | 36.1% [33.8-39.2] | 49.3% [46.1-51.3] | 0.18 | 0.23 | 0.31 | 0.69 | 0.33 | 0.43 | 0.58 | 1.28 |
| sens/adhoc_frac=0.15 | 11.2% [10.1-13.7] | 15.6% [14.5-17.6] | 21.0% [19.9-22.4] | 35.4% [34.2-36.6] | 0.13 | 0.17 | 0.24 | 0.53 | 0.30 | 0.40 | 0.55 | 1.25 |

### Arm comparison at medium / 30% private (mean over seeds)

| arm | effective-label mass <=3 | entries | compute vs per-user | compute vs old shared | note |
|---|---|---|---|---|---|
| base (intersection label) | 59.3% [51.8-63.5] | 80,777 | 0.45 | 1.00 | fails |
| A LMF (rho .15) | 27.5% [25.5-30.9] | 141,179 | 0.19 | 0.42 | passes; join is the only narrow-label work |
| B group-closure cover | 75.7% [65.5-82.2] | 121,102 | 0.70 | 1.55 | cover is a subset of the intersection, so it can only shrink audiences |
| C class-partial | 21.9% [20.0-25.6] (same labels as A) | 268,784 | 0.50 | 1.13 | same label benefit, but no cross-artifact reuse |

### Hybrid H: LMF only for narrow artifacts, wide ones stay monolithic (rho = 0.15)

| scenario | before | pure LMF M2 | H(T=3) M2 | H(T=3) share of artifact reads on LMF path | H(T=3) compute / per-user | H(T=3) compute / old shared | H(T=10) M2 | H(T=10) share on LMF path | H(T=10) compute / per-user | H(T=10) compute / old shared |
|---|---|---|---|---|---|---|---|---|---|---|
| medium/priv05 | 40.8% [33.6-49.6] | 10.3% [8.5-12.7] | 11.0% [9.2-13.6] | 41% [34-50] | 0.27 | 0.77 | 10.9% [9.1-13.4] | 49% [43-55] | 0.24 | 0.70 |
| medium/priv30 | 59.3% [51.8-63.5] | 27.5% [25.5-30.9] | 28.8% [26.8-32.3] | 59% [52-64] | 0.30 | 0.66 | 28.5% [26.6-32.1] | 68% [64-74] | 0.28 | 0.61 |
| many_small/priv30 | 60.1% [53.1-64.1] | 28.9% [25.0-33.0] | 30.2% [25.9-34.3] | 60% [53-64] | 0.33 | 0.64 | 29.9% [25.7-33.9] | 70% [62-79] | 0.30 | 0.59 |
| few_large/priv30 | 56.6% [54.4-62.6] | 24.8% [21.8-27.2] | 26.2% [23.0-28.8] | 57% [54-63] | 0.27 | 0.71 | 26.0% [22.9-28.6] | 62% [59-68] | 0.25 | 0.66 |
| combo/worst_case | 65.5% [58.1-68.1] | 31.3% [28.6-34.6] | 32.4% [29.5-35.8] | 66% [58-68] | 0.33 | 0.62 | 32.1% [29.3-35.4] | 75% [69-81] | 0.31 | 0.57 |
| sens/adhoc_frac=0.15 | 54.0% [52.1-56.4] | 15.6% [14.5-17.6] | 16.4% [15.3-18.6] | 54% [52-56] | 0.29 | 0.68 | 16.2% [15.2-18.3] | 66% [59-73] | 0.26 | 0.61 |
