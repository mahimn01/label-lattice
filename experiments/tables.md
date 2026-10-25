### Baseline scenario (medium structure, 5% private docs), mean [min–max] over 5 seeds

| Measure | Value |
|---|---|
| (a) distinct entitlement signatures (effective group set), of 10,000 users | 9,859 [9,831–9,912] |
| (a) same, counting only groups that appear in some ACL | 9,859 [9,831–9,912] |
| (a) same, plus users with an individual grant (private/ad-hoc doc) made unique | 9,994 [9,990–9,998] |
| (a) users alone in their signature class | 97.6% [97.2–98.4] |
| (b) distinct document labels — by ACL set (symbolic) | 28,820 [28,641–28,915] |
| (b) distinct document labels — by audience (canonical) | 27,941 [27,760–28,058] |
| (c) distinct derived-artifact labels — symbolic (set of input ACLs) | 55,345 [54,459–56,107] |
| (c) distinct derived-artifact labels — by audience (canonical) | 19,028 [18,676–19,515] |
| (d) median principals per doc label (over distinct labels) | 37.0 [34.0–39.0] |
| (d) median principals per artifact label | 3.0 [3.0–3.0] |
| (d) share of distinct doc labels with ≤3 principals | 27.9% [27.6–28.3] |
| (d) share of distinct artifact labels with ≤3 principals | 51.4% [50.1–52.2] |
| (e) doc read mass on items with audience ≥2 (potential sharing) | 93.4% [88.5–95.8] |
| (e) doc read mass on items actually read by ≥2 distinct users in the log (realized) | 92.9% [88.0–95.3] |
| (e) lazy hit rate: per-user cache / shared label-keyed store (eager = 100%) | 64.2% [63.6–64.7] / 96.2% [96.2–96.2] |
| (e) storage ratio per-user store ÷ shared store (docs) | 9.34 [9.19–9.50]× |
| (f) doc read mass needing label audience ≤3 principals  [falsifier: ≥50% ⇒ drop] | **8.5% [6.0–13.7]** → PASS |
| (g) artifact read mass on labels with ≤3 principals | **40.8% [33.6–49.6]** → PASS |
| (g) artifact read mass realized shared (≥2 users) / storage ratio | 70.3% [64.4–74.2] / 3.17 [2.95–3.33]× |
| (g) artifacts: median audience ÷ smallest input audience | 0.60 [0.50–0.86] |

#### (d) Distribution of label audience sizes, baseline (seed mean)

| Principals per label | # distinct doc labels | doc read mass | # distinct artifact labels | artifact read mass |
|---|---|---|---|---|
| 1 | 4,505 | 6.6% | 5,782 | 27.1% |
| 2 | 1,668 | 1.1% | 2,572 | 10.5% |
| 3 | 1,629 | 0.9% | 1,426 | 3.2% |
| 4-10 | 3,872 | 4.9% | 3,695 | 8.2% |
| 11-100 | 6,274 | 19.1% | 4,162 | 23.6% |
| 101-1000 | 8,945 | 43.9% | 1,265 | 24.5% |
| 1001-5000 | 1,047 | 16.6% | 126 | 2.7% |
| 5001-9999 | 0 | 0.0% | 0 | 0.0% |
| 10000 (all) | 1 | 7.1% | 1 | 0.2% |

### Sweep: private-doc fraction × ACL structure (5 seeds; mean [min–max]; verdict vs 50% threshold)

**Structure: few_large — few large groups**

| private docs | signatures | doc labels (aud.) | artifact labels (aud.) | doc realized-shared mass | storage ratio (docs) | (f) doc mass ≤3 | (f) verdict | (g) artifact mass ≤3 | (g) verdict |
|---|---|---|---|---|---|---|---|---|---|
| 0% | 8,134 | 9,699 | 20,614 | 99.5% [99.5–99.5] | 11.5× | 2.7% [1.0–8.8] | PASS | 21.0% [20.1–22.8] | PASS |
| 5% | 8,134 | 14,089 | 20,787 | 93.3% [88.2–96.2] | 11.0× | 7.5% [4.7–13.1] | PASS | 28.6% [26.0–32.3] | PASS |
| 10% | 8,134 | 15,624 | 20,761 | 89.1% [84.4–91.7] | 10.4× | 11.8% [8.9–16.8] | PASS | 33.0% [29.5–37.7] | PASS |
| 20% | 8,134 | 16,982 | 20,176 | 79.6% [76.8–82.8] | 9.3× | 21.1% [17.9–24.7] | PASS | 42.2% [37.6–52.2] | MIXED (4/5 pass) |
| 30% | 8,134 | 17,538 | 18,824 | 71.6% [69.1–75.4] | 8.2× | 29.4% [25.5–32.4] | PASS | 56.6% [54.4–62.6] | FAIL |
| 40% | 8,134 | 17,828 | 17,514 | 61.5% [57.2–65.0] | 7.1× | 39.6% [36.2–45.1] | PASS | 63.2% [50.1–71.5] | FAIL |
| 50% | 8,134 | 17,935 | 15,617 | 50.9% [44.8–57.2] | 5.9× | 50.3% [43.5–57.0] | MIXED (2/5 pass) | 66.4% [59.5–78.5] | FAIL |
| 60% | 8,134 | 17,977 | 13,331 | 41.4% [36.7–49.7] | 4.8× | 61.2% [56.7–64.5] | FAIL | 80.3% [73.8–86.6] | FAIL |
| 70% | 8,134 | 17,610 | 10,468 | 30.4% [25.8–35.2] | 3.7× | 71.5% [66.2–75.9] | FAIL | 84.6% [75.7–90.9] | FAIL |
| 80% | 8,134 | 16,877 | 8,928 | 20.8% [15.9–27.2] | 2.7× | 81.5% [78.3–85.4] | FAIL | 92.8% [90.5–96.7] | FAIL |

**Structure: medium — medium (baseline)**

| private docs | signatures | doc labels (aud.) | artifact labels (aud.) | doc realized-shared mass | storage ratio (docs) | (f) doc mass ≤3 | (f) verdict | (g) artifact mass ≤3 | (g) verdict |
|---|---|---|---|---|---|---|---|---|---|
| 0% | 9,859 | 23,962 | 19,340 | 99.2% [99.1–99.3] | 9.8× | 3.5% [1.7–9.5] | PASS | 29.4% [26.5–34.0] | PASS |
| 5% | 9,859 | 27,941 | 19,028 | 92.9% [88.0–95.3] | 9.3× | 8.5% [6.0–13.7] | PASS | 40.8% [33.6–49.6] | PASS |
| 10% | 9,859 | 29,159 | 18,899 | 87.9% [80.2–91.4] | 8.9× | 13.4% [9.8–21.5] | PASS | 45.0% [37.5–55.6] | MIXED (4/5 pass) |
| 20% | 9,859 | 29,915 | 18,003 | 78.6% [72.6–82.6] | 7.9× | 22.9% [18.8–29.8] | PASS | 50.2% [45.3–54.0] | MIXED (2/5 pass) |
| 30% | 9,859 | 29,805 | 16,684 | 71.5% [68.7–75.2] | 6.9× | 30.2% [26.3–33.2] | PASS | 59.3% [51.8–63.5] | FAIL |
| 40% | 9,859 | 29,173 | 15,436 | 60.8% [57.5–64.3] | 6.0× | 41.1% [36.9–45.8] | PASS | 66.9% [61.4–71.3] | FAIL |
| 50% | 9,859 | 28,330 | 13,748 | 50.5% [44.6–56.9] | 5.0× | 51.5% [44.2–58.0] | MIXED (2/5 pass) | 78.7% [73.0–83.1] | FAIL |
| 60% | 9,859 | 27,357 | 11,986 | 41.2% [36.7–49.5] | 4.0× | 62.0% [57.5–65.4] | FAIL | 81.3% [72.6–84.6] | FAIL |
| 70% | 9,859 | 25,614 | 9,570 | 30.3% [25.2–35.0] | 3.0× | 72.4% [66.9–76.9] | FAIL | 87.7% [85.0–90.7] | FAIL |
| 80% | 9,859 | 22,251 | 8,432 | 20.4% [15.4–26.4] | 2.3× | 82.5% [79.1–86.8] | FAIL | 93.6% [91.4–95.5] | FAIL |

**Structure: many_small — many small groups**

| private docs | signatures | doc labels (aud.) | artifact labels (aud.) | doc realized-shared mass | storage ratio (docs) | (f) doc mass ≤3 | (f) verdict | (g) artifact mass ≤3 | (g) verdict |
|---|---|---|---|---|---|---|---|---|---|
| 0% | 9,996 | 33,064 | 18,264 | 97.7% [96.9–98.4] | 8.9× | 7.2% [4.8–12.8] | PASS | 38.6% [32.3–47.1] | PASS |
| 5% | 9,996 | 36,302 | 17,940 | 90.2% [86.3–93.9] | 8.4× | 13.2% [10.3–16.6] | PASS | 43.4% [36.5–49.2] | PASS |
| 10% | 9,996 | 36,994 | 17,732 | 89.0% [87.3–90.7] | 8.0× | 15.4% [12.2–20.2] | PASS | 50.9% [42.2–61.1] | MIXED (2/5 pass) |
| 20% | 9,996 | 36,822 | 16,737 | 76.7% [72.7–81.8] | 7.2× | 26.3% [20.8–31.0] | PASS | 65.7% [62.2–70.0] | FAIL |
| 30% | 9,996 | 35,724 | 15,596 | 70.6% [67.9–74.0] | 6.2× | 33.4% [29.8–36.3] | PASS | 60.1% [53.1–64.1] | FAIL |
| 40% | 9,996 | 34,404 | 14,510 | 59.9% [55.5–64.6] | 5.4× | 43.5% [38.8–48.6] | PASS | 70.7% [61.0–76.2] | FAIL |
| 50% | 9,996 | 32,691 | 12,730 | 49.5% [42.5–56.0] | 4.5× | 53.8% [46.8–60.2] | MIXED (2/5 pass) | 76.2% [64.2–84.8] | FAIL |
| 60% | 9,996 | 30,695 | 11,224 | 39.8% [35.5–48.6] | 3.6× | 65.2% [62.0–68.4] | FAIL | 86.5% [83.1–88.6] | FAIL |
| 70% | 9,996 | 27,755 | 9,202 | 28.8% [23.3–32.8] | 2.8× | 75.3% [72.6–79.4] | FAIL | 91.0% [89.2–93.5] | FAIL |
| 80% | 9,996 | 23,490 | 8,275 | 20.2% [15.0–26.8] | 2.1× | 84.0% [79.9–87.2] | FAIL | 92.5% [84.9–97.0] | FAIL |

### Sensitivity (medium structure unless noted; baseline = 5% private, 25% small-group, 3% ad-hoc, Zipf 1.0, creator-coherent artifacts)

| scenario | parameters | (f) doc mass ≤3 | (f) | (g) artifact mass ≤3 | (g) | doc realized-shared | doc storage ratio | signatures |
|---|---|---|---|---|---|---|---|---|
| grid/medium/priv05 | struct=medium, priv=5%, small=25%, adhoc=3%, popmult=1.0, zipf=1.0, art=creator, localproj=0.65 | 8.5% [6.0–13.7] | PASS | 40.8% [33.6–49.6] | PASS | 92.9% [88.0–95.3] | 9.3× | 9,859 |
| sens/small_frac=0.0 | struct=medium, priv=5%, small=0%, adhoc=3%, popmult=1.0, zipf=1.0, art=creator, localproj=0.65 | 7.8% [5.0–13.1] | PASS | 25.6% [23.2–30.3] | PASS | 93.2% [88.2–95.8] | 9.9× | 9,859 |
| sens/small_frac=0.5 | struct=medium, priv=5%, small=50%, adhoc=3%, popmult=1.0, zipf=1.0, art=creator, localproj=0.65 | 9.7% [6.8–14.6] | PASS | 47.1% [39.3–51.6] | MIXED (3/5 pass) | 92.7% [87.7–95.4] | 8.8× | 9,859 |
| sens/small_frac=0.75 | struct=medium, priv=5%, small=75%, adhoc=3%, popmult=1.0, zipf=1.0, art=creator, localproj=0.65 | 10.1% [7.3–15.2] | PASS | 44.1% [40.4–53.2] | MIXED (4/5 pass) | 92.5% [87.3–95.1] | 8.2× | 9,859 |
| sens/adhoc_frac=0.0 | struct=medium, priv=5%, small=25%, adhoc=0%, popmult=1.0, zipf=1.0, art=creator, localproj=0.65 | 7.3% [4.7–11.9] | PASS | 34.7% [25.2–43.1] | PASS | 93.0% [88.0–95.6] | 9.6× | 9,859 |
| sens/adhoc_frac=0.15 | struct=medium, priv=5%, small=25%, adhoc=15%, popmult=1.0, zipf=1.0, art=creator, localproj=0.65 | 13.5% [9.8–19.0] | PASS | 54.0% [52.1–56.4] | FAIL | 92.6% [87.6–95.4] | 8.3× | 9,859 |
| sens/priv20_pop_mult=0.25 | struct=medium, priv=20%, small=25%, adhoc=3%, popmult=0.25, zipf=1.0, art=creator, localproj=0.65 | 9.3% [7.1–15.2] | PASS | 38.3% [32.4–48.1] | PASS | 92.5% [87.8–94.6] | 9.3× | 9,859 |
| sens/priv20_pop_mult=4.0 | struct=medium, priv=20%, small=25%, adhoc=3%, popmult=4.0, zipf=1.0, art=creator, localproj=0.65 | 51.6% [46.1–58.4] | MIXED (3/5 pass) | 75.5% [62.5–84.1] | FAIL | 49.1% [42.6–54.6] | 5.8× | 9,859 |
| sens/priv50_pop_mult=0.25 | struct=medium, priv=50%, small=25%, adhoc=3%, popmult=0.25, zipf=1.0, art=creator, localproj=0.65 | 23.6% [17.9–28.9] | PASS | 55.1% [48.9–63.7] | MIXED (1/5 pass) | 79.8% [76.2–83.9] | 7.4× | 9,859 |
| sens/priv50_pop_mult=4.0 | struct=medium, priv=50%, small=25%, adhoc=3%, popmult=4.0, zipf=1.0, art=creator, localproj=0.65 | 80.1% [75.5–84.0] | FAIL | 93.5% [88.7–95.8] | FAIL | 20.5% [16.4–24.7] | 2.9× | 9,859 |
| sens/art_mode=random | struct=medium, priv=5%, small=25%, adhoc=3%, popmult=1.0, zipf=1.0, art=random, localproj=0.65 | 8.5% [6.0–13.7] | PASS | 25.8% [15.3–38.6] | PASS | 92.9% [88.0–95.3] | 9.3× | 9,859 |
| sens/doc_zipf=0.7 | struct=medium, priv=5%, small=25%, adhoc=3%, popmult=1.0, zipf=0.7, art=creator, localproj=0.65 | 7.9% [7.5–8.3] | PASS | 53.8% [49.1–59.8] | MIXED (2/5 pass) | 94.4% [94.0–94.8] | 15.8× | 9,859 |
| sens/doc_zipf=1.3 | struct=medium, priv=5%, small=25%, adhoc=3%, popmult=1.0, zipf=1.3, art=creator, localproj=0.65 | 10.0% [3.3–29.3] | PASS | 20.7% [9.1–36.0] | PASS | 90.3% [71.5–96.7] | 6.4× | 9,859 |
| sens/local_proj_prob=0.2 | struct=medium, priv=5%, small=25%, adhoc=3%, popmult=1.0, zipf=1.0, art=creator, localproj=0.2 | 8.9% [5.9–13.9] | PASS | 43.2% [33.1–50.3] | MIXED (3/5 pass) | 93.0% [88.0–95.3] | 9.5× | 9,981 |
| sens/local_proj_prob=0.95 | struct=medium, priv=5%, small=25%, adhoc=3%, popmult=1.0, zipf=1.0, art=creator, localproj=0.95 | 8.9% [6.3–13.8] | PASS | 39.0% [33.3–45.4] | PASS | 92.9% [88.0–95.1] | 9.1× | 9,572 |
| combo/worst_case | struct=many_small, priv=20%, small=50%, adhoc=10%, popmult=1.0, zipf=1.0, art=creator, localproj=0.65 | 30.8% [24.3–36.0] | PASS | 65.5% [58.1–68.1] | FAIL | 76.0% [73.1–80.9] | 6.2× | 9,996 |
| combo/best_case | struct=few_large, priv=0%, small=10%, adhoc=0%, popmult=1.0, zipf=1.0, art=creator, localproj=0.65 | 0.0% [0.0–0.0] | PASS | 9.7% [6.9–11.5] | PASS | 99.6% [99.6–99.6] | 12.0× | 8,134 |
| grid/medium/priv20 | struct=medium, priv=20%, small=25%, adhoc=3%, popmult=1.0, zipf=1.0, art=creator, localproj=0.65 | 22.9% [18.8–29.8] | PASS | 50.2% [45.3–54.0] | MIXED (2/5 pass) | 78.6% [72.6–82.6] | 7.9× | 9,859 |
| grid/medium/priv50 | struct=medium, priv=50%, small=25%, adhoc=3%, popmult=1.0, zipf=1.0, art=creator, localproj=0.65 | 51.5% [44.2–58.0] | MIXED (2/5 pass) | 78.7% [73.0–83.1] | FAIL | 50.5% [44.6–56.9] | 5.0× | 9,859 |
