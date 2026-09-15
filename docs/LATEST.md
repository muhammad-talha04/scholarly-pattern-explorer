# Weekly snapshot

_Generated 2026-09-15 20:12. Corpus: 188,968 papers, 319,237 authors,
2,369 topics, publication years 2000-2026._

![papers per year](charts/papers_per_year.png)

## Emerging topic pairs
| itemset | first_window | first_support | last_window | last_support | change |
|---|---|---|---|---|---|
| AI in cancer detection | Radiomics and Machine Learning in Medical Imaging | 2014 | 0.0054 | 2024 | 0.0411 | 0.0357 |
| Cryptography and Data Security | Privacy-Preserving Technologies in Data | 2004 | 0.0059 | 2024 | 0.0305 | 0.0246 |
| Anomaly Detection Techniques and Applications | Network Security and Intrusion Detection | 2014 | 0.0055 | 2024 | 0.0244 | 0.0189 |
| Energy Load and Power Forecasting | Solar Radiation and Photovoltaics | 2013 | 0.0063 | 2024 | 0.0243 | 0.018 |
| Photovoltaic System Optimization Techniques | Solar Radiation and Photovoltaics | 2000 | 0.0083 | 2024 | 0.0249 | 0.0167 |
| Artificial Intelligence in Healthcare and Education | Machine Learning in Healthcare | 2020 | 0.0053 | 2024 | 0.0199 | 0.0147 |
| AI in Service Interactions | Digital Marketing and Social Media | 2019 | 0.0052 | 2024 | 0.0182 | 0.013 |
| Machine Learning in Healthcare | Topic Modeling | 2018 | 0.0057 | 2024 | 0.0169 | 0.0112 |
| Energy Load and Power Forecasting | Photovoltaic System Optimization Techniques | Solar Radiation and Photovoltaics | 2015 | 0.0066 | 2024 | 0.0174 | 0.0108 |
| Energy Load and Power Forecasting | Photovoltaic System Optimization Techniques | 2015 | 0.0066 | 2024 | 0.0174 | 0.0108 |

![lifecycles](charts/pattern_lifecycles.png)

## Declining topic pairs
| itemset | first_window | first_support | last_window | last_support | change |
|---|---|---|---|---|---|
| Quantum Information and Cryptography | Quantum Mechanics and Applications | 2000 | 0.0853 | 2024 | 0.0251 | -0.0602 |
| Quantum Computing Algorithms and Architecture | Quantum Mechanics and Applications | 2000 | 0.0575 | 2024 | 0.02 | -0.0375 |
| Quantum Computing Algorithms and Architecture | Quantum Information and Cryptography | Quantum Mechanics and Applications | 2000 | 0.0566 | 2024 | 0.0191 | -0.0375 |
| Logic, Reasoning, and Knowledge | Logic, programming, and type systems | 2000 | 0.0344 | 2016 | 0.0062 | -0.0282 |
| Fuzzy Logic and Control Systems | Neural Networks and Applications | 2000 | 0.0336 | 2020 | 0.0058 | -0.0278 |
| Quantum Computing Algorithms and Architecture | Quantum Information and Cryptography | 2000 | 0.085 | 2024 | 0.0657 | -0.0193 |
| Logic, Reasoning, and Knowledge | Semantic Web and Ontologies | 2000 | 0.0255 | 2015 | 0.0068 | -0.0187 |
| Formal Methods in Verification | Logic, programming, and type systems | 2000 | 0.0247 | 2015 | 0.0061 | -0.0186 |
| Logic, Reasoning, and Knowledge | Multi-Agent Systems and Negotiation | 2000 | 0.0237 | 2016 | 0.006 | -0.0177 |
| Natural Language Processing Techniques | Speech and dialogue systems | 2000 | 0.0204 | 2018 | 0.005 | -0.0154 |

## Strongest patterns in 2024-2026
| itemset | k | support_count | n_tx | support |
|---|---|---|---|---|
| Quantum Computing Algorithms and Architecture | Quantum Information and Cryptography | 2 | 620 | 9432 | 0.06573367260390162 |
| Natural Language Processing Techniques | Topic Modeling | 2 | 424 | 9432 | 0.04495335029686175 |
| AI in cancer detection | Radiomics and Machine Learning in Medical Imaging | 2 | 388 | 9432 | 0.041136556403731976 |
| Cryptography and Data Security | Privacy-Preserving Technologies in Data | 2 | 288 | 9432 | 0.030534351145038167 |
| Quantum Information and Cryptography | Quantum Mechanics and Applications | 2 | 237 | 9432 | 0.025127226463104325 |
| Photovoltaic System Optimization Techniques | Solar Radiation and Photovoltaics | 2 | 235 | 9432 | 0.02491518235793045 |
| Anomaly Detection Techniques and Applications | Network Security and Intrusion Detection | 2 | 230 | 9432 | 0.02438507209499576 |
| Energy Load and Power Forecasting | Solar Radiation and Photovoltaics | 2 | 229 | 9432 | 0.02427905004240882 |
| Evolutionary Algorithms and Applications | Metaheuristic Optimization Algorithms Research | 2 | 212 | 9432 | 0.022476675148430873 |
| Quantum Computing Algorithms and Architecture | Quantum Mechanics and Applications | 2 | 189 | 9432 | 0.020038167938931296 |

## Collaboration network, 2024-2026
| author | collaborators | joint_papers |
|---|---|---|
| Andreas Bengtsson | 29 | 123 |
| Brian Burkett | 26 | 106 |
| Alejandro Grajales Dau | 24 | 98 |
| Hung-Shen Chang | 24 | 98 |
| Ilya Drozdov | 20 | 80 |
| Jonathan A. Gross | 20 | 80 |
| Sean D. Harrington | 20 | 80 |
| Abraham Asfaw | 19 | 76 |
| Agustín Di Paolo | 19 | 76 |
| Raja Gosula | 19 | 76 |

![network](charts/coauthor_network.png)

## Link prediction
| model | auc | ap |
|---|---|---|
| graph-mlp | 0.8877309 | 0.90382195 |
| pa | 0.81989866 | 0.83520025 |
| topic | 0.81543314 | 0.7964251 |
| node2vec | 0.6926468 | 0.72290975 |
| aa | 0.6135961 | 0.6135774 |
| cn | 0.6135938 | 0.613543 |
| jaccard | 0.61358845 | 0.61354333 |

![auc](charts/link_model_auc.png)

Top predicted collaborations: [data/predicted_collaborations.csv](data/predicted_collaborations.csv)
