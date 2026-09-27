# Weekly snapshot

_Generated 2026-09-27 10:00. Corpus: 2,784 papers, 13,162 authors,
866 topics, publication years 2023-2026._

![papers per year](charts/papers_per_year.png)

## Emerging topic pairs
| itemset | first_window | first_support | last_window | last_support | change |
|---|---|---|---|---|---|
| Anomaly Detection Techniques and Applications | Network Security and Intrusion Detection | 2023 | 0.0265 | 2024 | 0.0296 | 0.0031 |
| Advanced Malware Detection Techniques | Network Security and Intrusion Detection | 2023 | 0.025 | 2024 | 0.0263 | 0.0014 |
| Blockchain Technology Applications and Security | IoT and Edge/Fog Computing | 2023 | 0.0208 | 2023 | 0.0208 | 0.0 |
| Cryptography and Data Security | Privacy-Preserving Technologies in Data | 2023 | 0.0208 | 2024 | 0.0207 | -0.0001 |
| Quantum Computing Algorithms and Architecture | Quantum Information and Cryptography | 2023 | 0.045 | 2024 | 0.0423 | -0.0026 |

![lifecycles](charts/pattern_lifecycles.png)

## Declining topic pairs
| itemset | first_window | first_support | last_window | last_support | change |
|---|---|---|---|---|---|
| Quantum Computing Algorithms and Architecture | Quantum Information and Cryptography | 2023 | 0.045 | 2024 | 0.0423 | -0.0026 |
| Cryptography and Data Security | Privacy-Preserving Technologies in Data | 2023 | 0.0208 | 2024 | 0.0207 | -0.0001 |
| Blockchain Technology Applications and Security | IoT and Edge/Fog Computing | 2023 | 0.0208 | 2023 | 0.0208 | 0.0 |
| Advanced Malware Detection Techniques | Network Security and Intrusion Detection | 2023 | 0.025 | 2024 | 0.0263 | 0.0014 |
| Anomaly Detection Techniques and Applications | Network Security and Intrusion Detection | 2023 | 0.0265 | 2024 | 0.0296 | 0.0031 |

## Strongest patterns in 2024-2026
| itemset | k | support_count | n_tx | support |
|---|---|---|---|---|
| Quantum Computing Algorithms and Architecture | Quantum Information and Cryptography | 2 | 90 | 2126 | 0.04233301975540922 |
| Anomaly Detection Techniques and Applications | Network Security and Intrusion Detection | 2 | 63 | 2126 | 0.029633113828786452 |
| Advanced Malware Detection Techniques | Network Security and Intrusion Detection | 2 | 56 | 2126 | 0.02634054562558796 |
| Cryptography and Data Security | Privacy-Preserving Technologies in Data | 2 | 44 | 2126 | 0.020696142991533398 |

## Collaboration network, 2024-2026
| author | collaborators | joint_papers |
|---|---|---|
| Xuemin Shen | 20 | 111 |
| Habib Hamam | 15 | 83 |
| Dusit Tao Niyato | 14 | 92 |
| Jiawen Kang | 13 | 72 |
| Roberto Morandotti | 13 | 41 |
| F. Richard Yu | 11 | 41 |
| David Moss | 11 | 32 |
| Robert L. Moore | 11 | 22 |
| Hongyang Du | 9 | 60 |
| Witold Pedrycz | 9 | 36 |

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
