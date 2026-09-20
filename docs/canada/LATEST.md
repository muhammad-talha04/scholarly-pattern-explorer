# Weekly snapshot

_Generated 2026-09-20 09:15. Corpus: 2,743 papers, 12,947 authors,
860 topics, publication years 2023-2026._

![papers per year](charts/papers_per_year.png)

## Emerging topic pairs
| itemset | first_window | first_support | last_window | last_support | change |
|---|---|---|---|---|---|
| Anomaly Detection Techniques and Applications | Network Security and Intrusion Detection | 2023 | 0.0269 | 2024 | 0.0301 | 0.0032 |
| Advanced Malware Detection Techniques | Network Security and Intrusion Detection | 2023 | 0.0249 | 2024 | 0.0263 | 0.0013 |
| Cryptography and Data Security | Privacy-Preserving Technologies in Data | 2023 | 0.021 | 2024 | 0.021 | 0.0 |
| Blockchain Technology Applications and Security | IoT and Edge/Fog Computing | 2023 | 0.021 | 2023 | 0.021 | 0.0 |
| Quantum Computing Algorithms and Architecture | Quantum Information and Cryptography | 2023 | 0.0452 | 2024 | 0.0425 | -0.0027 |

![lifecycles](charts/pattern_lifecycles.png)

## Declining topic pairs
| itemset | first_window | first_support | last_window | last_support | change |
|---|---|---|---|---|---|
| Quantum Computing Algorithms and Architecture | Quantum Information and Cryptography | 2023 | 0.0452 | 2024 | 0.0425 | -0.0027 |
| Blockchain Technology Applications and Security | IoT and Edge/Fog Computing | 2023 | 0.021 | 2023 | 0.021 | 0.0 |
| Cryptography and Data Security | Privacy-Preserving Technologies in Data | 2023 | 0.021 | 2024 | 0.021 | 0.0 |
| Advanced Malware Detection Techniques | Network Security and Intrusion Detection | 2023 | 0.0249 | 2024 | 0.0263 | 0.0013 |
| Anomaly Detection Techniques and Applications | Network Security and Intrusion Detection | 2023 | 0.0269 | 2024 | 0.0301 | 0.0032 |

## Strongest patterns in 2024-2026
| itemset | k | support_count | n_tx | support |
|---|---|---|---|---|
| Quantum Computing Algorithms and Architecture | Quantum Information and Cryptography | 2 | 89 | 2095 | 0.04248210023866349 |
| Anomaly Detection Techniques and Applications | Network Security and Intrusion Detection | 2 | 63 | 2095 | 0.03007159904534606 |
| Advanced Malware Detection Techniques | Network Security and Intrusion Detection | 2 | 55 | 2095 | 0.026252983293556086 |
| Cryptography and Data Security | Privacy-Preserving Technologies in Data | 2 | 44 | 2095 | 0.02100238663484487 |

## Collaboration network, 2024-2026
| author | collaborators | joint_papers |
|---|---|---|
| Xuemin Shen | 19 | 109 |
| Dusit Niyato | 19 | 108 |
| Habib Hamam | 14 | 81 |
| Jiawen Kang | 13 | 75 |
| F. Richard Yu | 11 | 41 |
| Witold Pedrycz | 11 | 40 |
| Rongxing Lu | 10 | 40 |
| Roberto Morandotti | 10 | 35 |
| Hongyang Du | 9 | 60 |
| Nicola Montaut | 9 | 25 |

![network](charts/coauthor_network.png)

## Link prediction
| model | auc | ap |
|---|---|---|
| graph-mlp | 0.91453636 | 0.9300244 |
| topic | 0.84341997 | 0.82834053 |
| pa | 0.81823343 | 0.8359255 |
| node2vec | 0.7564105 | 0.78495276 |
| aa | 0.6672695 | 0.6669321 |
| cn | 0.6672423 | 0.6668721 |
| jaccard | 0.6670818 | 0.6659139 |

![auc](charts/link_model_auc.png)

Top predicted collaborations: [data/predicted_collaborations.csv](data/predicted_collaborations.csv)
