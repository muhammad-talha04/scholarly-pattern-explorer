# Weekly snapshot

_Generated 2026-10-11 10:46. Corpus: 3,676 papers, 18,199 authors,
1,097 topics, publication years 2023-2026._

![papers per year](charts/papers_per_year.png)

## Emerging topic pairs
| itemset | first_window | first_support | last_window | last_support | change |
|---|---|---|---|---|---|
| Anomaly Detection Techniques and Applications | Network Security and Intrusion Detection | 2023 | 0.0207 | 2024 | 0.0228 | 0.002 |
| Advanced Malware Detection Techniques | Network Security and Intrusion Detection | 2024 | 0.0203 | 2024 | 0.0203 | 0.0 |
| Quantum Computing Algorithms and Architecture | Quantum Information and Cryptography | 2023 | 0.04 | 2024 | 0.0369 | -0.0032 |

![lifecycles](charts/pattern_lifecycles.png)

## Declining topic pairs
| itemset | first_window | first_support | last_window | last_support | change |
|---|---|---|---|---|---|
| Quantum Computing Algorithms and Architecture | Quantum Information and Cryptography | 2023 | 0.04 | 2024 | 0.0369 | -0.0032 |
| Advanced Malware Detection Techniques | Network Security and Intrusion Detection | 2024 | 0.0203 | 2024 | 0.0203 | 0.0 |
| Anomaly Detection Techniques and Applications | Network Security and Intrusion Detection | 2023 | 0.0207 | 2024 | 0.0228 | 0.002 |

## Strongest patterns in 2024-2026
| itemset | k | support_count | n_tx | support |
|---|---|---|---|---|
| Quantum Computing Algorithms and Architecture | Quantum Information and Cryptography | 2 | 107 | 2901 | 0.03688383316097897 |
| Anomaly Detection Techniques and Applications | Network Security and Intrusion Detection | 2 | 66 | 2901 | 0.022750775594622543 |
| Advanced Malware Detection Techniques | Network Security and Intrusion Detection | 2 | 59 | 2901 | 0.020337814546708032 |

## Collaboration network, 2024-2026
| author | collaborators | joint_papers |
|---|---|---|
| Xuemin Shen | 31 | 199 |
| Dusit Tao Niyato | 21 | 157 |
| Habib Hamam | 19 | 126 |
| Jiawen Kang | 16 | 111 |
| Hongyang Du | 12 | 96 |
| Fei Richard Yu | 12 | 48 |
| Witold Pedrycz | 12 | 48 |
| Tehseen Mazhar | 10 | 84 |
| Zehui Xiong | 10 | 81 |
| Trung Q. Duong | 9 | 45 |

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
