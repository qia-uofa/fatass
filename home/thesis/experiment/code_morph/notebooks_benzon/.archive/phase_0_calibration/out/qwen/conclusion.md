# Phase 0 calibration -- conclusion (qwen)

Model: `Qwen/Qwen2.5-7B-Instruct` (28 layers) -- profile `reduced`

## 1. TriviaQA -- full 9x6 matrix

n=100

|  | labeled correctness | answer logit | self challenge resistance | labeled challenge resistance | binary entropy | nonbinary logit |
| --- | --- | --- | --- | --- | --- | --- |
| confidence | 0.482 | 0.344 | 0.389 | 0.314 | -0.372 | 0.470 |
| commitment | 0.295 | 0.356 | 0.180 | 0.164 | -0.193 | 0.318 |
| commitment_defined | 0.250 | 0.367 | 0.159 | 0.102 | -0.188 | 0.350 |
| commitment_parallel | 0.274 | 0.320 | 0.137 | 0.120 | -0.212 | 0.355 |
| commitment_challenge | 0.102 | 0.207 | -0.029 | -0.113 | -0.228 | 0.274 |
| nuance | 0.172 | 0.101 | 0.133 | 0.062 | 0.003 | 0.007 |
| nuance_ambiguity | -0.066 | -0.109 | -0.225 | -0.302 | 0.221 | -0.167 |
| nuance_certainty | -0.250 | -0.358 | -0.250 | -0.241 | 0.148 | -0.359 |
| nuance_defined | 0.061 | 0.048 | -0.024 | -0.034 | 0.046 | -0.029 |

## 2. benzon:ontology_trivials -- full 9x6 matrix

n=65

|  | labeled correctness | answer logit | self challenge resistance | labeled challenge resistance | binary entropy | nonbinary logit |
| --- | --- | --- | --- | --- | --- | --- |
| confidence | 0.027 | 0.447 | 0.142 | 0.054 | -0.474 | -0.430 |
| commitment | NaN | NaN | NaN | NaN | NaN | NaN |
| commitment_defined | NaN | NaN | NaN | NaN | NaN | NaN |
| commitment_parallel | NaN | NaN | NaN | NaN | NaN | NaN |
| commitment_challenge | -0.032 | 0.113 | 0.013 | -0.013 | -0.213 | -0.207 |
| nuance | -0.096 | -0.481 | -0.132 | 0.116 | 0.301 | 0.287 |
| nuance_ambiguity | -0.151 | -0.464 | -0.180 | 0.229 | 0.310 | 0.474 |
| nuance_certainty | 0.024 | -0.429 | 0.013 | -0.015 | 0.568 | 0.436 |
| nuance_defined | -0.114 | -0.518 | -0.003 | 0.196 | 0.434 | 0.398 |

## New dataset: philpapers

n=20

|  | labeled correctness | answer logit | self challenge resistance | labeled challenge resistance | binary entropy | nonbinary logit | labeled entropy |
| --- | --- | --- | --- | --- | --- | --- | --- |
| confidence | -0.106 | 0.224 | 0.264 | 0.264 | 0.014 | -0.574 | -0.106 |
| commitment | -0.009 | 0.429 | 0.207 | 0.207 | -0.325 | -0.762 | -0.009 |
| commitment_defined | 0.065 | 0.419 | 0.081 | 0.081 | 0.084 | -0.698 | 0.065 |
| commitment_parallel | -0.042 | 0.435 | 0.120 | 0.120 | 0.147 | -0.652 | -0.042 |
| commitment_challenge | 0.062 | 0.461 | 0.120 | 0.120 | -0.071 | -0.690 | 0.062 |
| nuance | -0.219 | -0.099 | 0.259 | 0.259 | 0.060 | -0.219 | -0.219 |
| nuance_ambiguity | NaN | NaN | NaN | NaN | NaN | NaN | NaN |
| nuance_certainty | 0.206 | -0.255 | -0.049 | -0.049 | 0.255 | 0.376 | 0.206 |
| nuance_defined | 0.110 | -0.411 | -0.100 | -0.100 | 0.130 | 0.350 | 0.110 |

## New dataset: ethics_commonsense

n=20

|  | labeled correctness | answer logit | self challenge resistance | labeled challenge resistance | binary entropy | nonbinary logit |
| --- | --- | --- | --- | --- | --- | --- |
| confidence | 0.341 | 0.489 | -0.289 | 0.405 | -0.426 | -0.833 |
| commitment | 0.456 | 0.559 | -0.242 | 0.163 | -0.295 | -0.745 |
| commitment_defined | 0.298 | 0.588 | -0.074 | 0.193 | -0.269 | -0.590 |
| commitment_parallel | 0.208 | 0.378 | -0.219 | -0.020 | -0.378 | -0.298 |
| commitment_challenge | 0.086 | -0.062 | -0.128 | -0.213 | -0.483 | -0.378 |
| nuance | -0.285 | -0.587 | 0.341 | -0.360 | 0.114 | 0.643 |
| nuance_ambiguity | -0.553 | -0.607 | 0.304 | -0.629 | 0.065 | 0.694 |
| nuance_certainty | -0.638 | -0.411 | 0.351 | -0.631 | 0.190 | 0.751 |
| nuance_defined | -0.174 | -0.471 | 0.230 | -0.190 | 0.130 | 0.511 |

## New dataset: ethics_deontology

n=20

|  | labeled correctness | answer logit | self challenge resistance | labeled challenge resistance | binary entropy | nonbinary logit |
| --- | --- | --- | --- | --- | --- | --- |
| confidence | 0.253 | -0.056 | 0.053 | -0.075 | 0.051 | 0.332 |
| commitment | -0.168 | 0.338 | 0.100 | 0.259 | -0.378 | -0.378 |
| commitment_defined | -0.168 | 0.338 | 0.100 | 0.259 | -0.378 | -0.378 |
| commitment_parallel | NaN | NaN | NaN | NaN | NaN | NaN |
| commitment_challenge | 0.105 | 0.520 | 0.347 | 0.405 | -0.491 | -0.376 |
| nuance | -0.245 | 0.087 | 0.231 | 0.174 | 0.405 | 0.116 |
| nuance_ambiguity | -0.390 | -0.325 | 0.070 | -0.299 | 0.372 | 0.252 |
| nuance_certainty | -0.252 | -0.095 | 0.028 | 0.199 | 0.208 | 0.038 |
| nuance_defined | -0.245 | 0.145 | 0.058 | 0.289 | 0.173 | -0.087 |

## New dataset: ethics_justice

n=20

|  | labeled correctness | answer logit | self challenge resistance | labeled challenge resistance | binary entropy | nonbinary logit |
| --- | --- | --- | --- | --- | --- | --- |
| confidence | 0.228 | -0.298 | 0.339 | 0.339 | -0.298 | 0.179 |
| commitment | -0.101 | 0.260 | 0.336 | 0.228 | -0.477 | -0.499 |
| commitment_defined | NaN | NaN | NaN | NaN | NaN | NaN |
| commitment_parallel | NaN | NaN | NaN | NaN | NaN | NaN |
| commitment_challenge | 0.230 | 0.504 | 0.198 | 0.407 | -0.175 | -0.524 |
| nuance | 0.228 | -0.060 | -0.040 | 0.020 | 0.099 | -0.099 |
| nuance_ambiguity | NaN | NaN | NaN | NaN | NaN | NaN |
| nuance_certainty | -0.318 | -0.585 | -0.152 | -0.326 | 0.238 | 0.390 |
| nuance_defined | 0.228 | -0.231 | 0.116 | 0.159 | -0.116 | -0.347 |

## New dataset: ethics_virtue

n=20

|  | labeled correctness | answer logit | self challenge resistance | labeled challenge resistance | binary entropy | nonbinary logit |
| --- | --- | --- | --- | --- | --- | --- |
| confidence | 0.275 | 0.029 | 0.087 | -0.002 | -0.360 | -0.231 |
| commitment | 0.243 | 0.167 | 0.031 | -0.077 | -0.055 | -0.289 |
| commitment_defined | 0.065 | 0.362 | -0.034 | -0.080 | -0.369 | -0.297 |
| commitment_parallel | 0.299 | 0.179 | -0.259 | -0.378 | -0.219 | -0.139 |
| commitment_challenge | 0.477 | 0.167 | -0.041 | -0.203 | -0.437 | -0.673 |
| nuance | 0.087 | -0.131 | 0.154 | 0.127 | 0.254 | 0.266 |
| nuance_ambiguity | NaN | NaN | NaN | NaN | NaN | NaN |
| nuance_certainty | NaN | NaN | NaN | NaN | NaN | NaN |
| nuance_defined | 0.087 | -0.131 | 0.154 | 0.127 | 0.254 | 0.266 |

## New dataset: ethics_utilitarianism

n=20

|  | labeled correctness | answer logit | self challenge resistance | labeled challenge resistance | binary entropy | nonbinary logit |
| --- | --- | --- | --- | --- | --- | --- |
| confidence | -0.040 | -0.050 | 0.351 | 0.190 | 0.330 | 0.390 |
| commitment | 0.155 | 0.556 | -0.544 | -0.258 | -0.600 | -0.631 |
| commitment_defined | 0.367 | 0.491 | -0.362 | -0.333 | -0.376 | -0.405 |
| commitment_parallel | NaN | NaN | NaN | NaN | NaN | NaN |
| commitment_challenge | 0.094 | 0.619 | -0.399 | -0.097 | -0.850 | -0.779 |
| nuance | 0.250 | 0.520 | -0.116 | -0.116 | -0.202 | -0.318 |
| nuance_ambiguity | NaN | NaN | NaN | NaN | NaN | NaN |
| nuance_certainty | 0.094 | -0.210 | 0.401 | 0.311 | 0.491 | 0.511 |
| nuance_defined | NaN | 0.338 | 0.020 | -0.020 | -0.099 | -0.099 |

## Construct-level 3x3, per dataset

## triviaqa

|  | correctness | logit_challenge | entropy |
| --- | --- | --- | --- |
| confidence | 0.482 | 0.397 | -0.267 |
| commitment | 0.250 | 0.198 | -0.029 |
| nuance | -0.025 | -0.149 | 0.049 |

## ontology_trivials

|  | correctness | logit_challenge | entropy |
| --- | --- | --- | --- |
| confidence | 0.027 | 0.278 | -0.430 |
| commitment | -0.032 | -0.087 | -0.207 |
| nuance | -0.092 | -0.132 | 0.462 |

## synonyms

|  | correctness | logit_challenge | entropy |
| --- | --- | --- | --- |
| confidence | 0.528 | -0.081 | -0.442 |
| commitment | 0.149 | 0.100 | -0.352 |
| nuance | -0.651 | 0.008 | 0.493 |

## philpapers

|  | correctness | logit_challenge | entropy |
| --- | --- | --- | --- |
| confidence | -0.106 | 0.196 | -0.610 |
| commitment | -0.021 | 0.321 | -0.786 |
| nuance | 0.127 | -0.386 | 0.295 |

## ethics_commonsense

|  | correctness | logit_challenge | entropy |
| --- | --- | --- | --- |
| confidence | 0.341 | 0.156 | -0.843 |
| commitment | 0.331 | 0.044 | -0.720 |
| nuance | -0.441 | -0.156 | 0.747 |

## ethics_deontology

|  | correctness | logit_challenge | entropy |
| --- | --- | --- | --- |
| confidence | 0.253 | -0.187 | 0.169 |
| commitment | 0.087 | 0.488 | -0.384 |
| nuance | -0.458 | 0.175 | 0.168 |

## ethics_justice

|  | correctness | logit_challenge | entropy |
| --- | --- | --- | --- |
| confidence | 0.228 | 0.338 | 0.179 |
| commitment | 0.177 | 0.355 | -0.595 |
| nuance | -0.104 | -0.322 | 0.168 |

## ethics_virtue

|  | correctness | logit_challenge | entropy |
| --- | --- | --- | --- |
| confidence | 0.275 | 0.006 | -0.231 |
| commitment | 0.502 | -0.106 | -0.606 |
| nuance | 0.087 | 0.003 | 0.266 |

## ethics_utilitarianism

|  | correctness | logit_challenge | entropy |
| --- | --- | --- | --- |
| confidence | -0.040 | 0.350 | 0.390 |
| commitment | 0.147 | -0.060 | -0.778 |
| nuance | 0.179 | 0.132 | 0.310 |

## Merged 9x6 matrix -- all nine datasets pooled

n=405

|  | labeled correctness | answer logit | self challenge resistance | labeled challenge resistance | binary entropy | nonbinary logit |
| --- | --- | --- | --- | --- | --- | --- |
| confidence | 0.441 | 0.496 | 0.069 | 0.024 | -0.454 | -0.314 |
| commitment | 0.233 | 0.417 | -0.076 | -0.026 | -0.310 | -0.242 |
| commitment_defined | 0.203 | 0.345 | -0.034 | -0.016 | -0.251 | -0.208 |
| commitment_parallel | 0.197 | 0.229 | -0.027 | -0.013 | -0.164 | -0.144 |
| commitment_challenge | 0.211 | 0.428 | -0.108 | -0.053 | -0.286 | -0.209 |
| nuance | -0.188 | -0.328 | 0.129 | 0.145 | 0.189 | 0.143 |
| nuance_ambiguity | -0.281 | -0.361 | -0.027 | 0.017 | 0.232 | 0.193 |
| nuance_certainty | -0.346 | -0.505 | 0.051 | 0.089 | 0.239 | 0.099 |
| nuance_defined | -0.249 | -0.379 | 0.124 | 0.219 | 0.161 | 0.042 |

## Merged construct-level 3x3 -- all nine datasets pooled

n=405

|  | correctness | logit_challenge | entropy |
| --- | --- | --- | --- |
| confidence | 0.441 | 0.192 | -0.371 |
| commitment | 0.268 | 0.112 | -0.283 |
| nuance | -0.327 | -0.018 | 0.126 |

## Best OM/GT per construct -- machinewise vs. humanwise

|  | dataset | construct | machine_om | machine_gt | machine_rho | human_om | human_rho |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 0 | triviaqa | confidence | confidence | nonbinary logit | 0.470 | confidence | 0.482 |
| 1 | triviaqa | commitment | commitment_defined | answer logit | 0.367 | commitment | 0.295 |
| 2 | triviaqa | nuance | nuance_certainty | nonbinary logit | -0.359 | nuance_certainty | -0.250 |
| 3 | ontology_trivials | confidence | confidence | binary entropy | -0.474 | confidence | 0.027 |
| 4 | ontology_trivials | commitment | commitment_challenge | binary entropy | -0.213 | commitment_challenge | -0.032 |
| 5 | ontology_trivials | nuance | nuance_certainty | binary entropy | 0.568 | nuance_ambiguity | -0.151 |
| 6 | synonyms | confidence | confidence | answer logit | 0.544 | confidence | 0.528 |
| 7 | synonyms | commitment | commitment_challenge | nonbinary logit | -0.404 | commitment_challenge | 0.149 |
| 8 | synonyms | nuance | nuance_certainty | answer logit | -0.520 | nuance_defined | -0.670 |
| 9 | philpapers | confidence | confidence | nonbinary logit | -0.574 | confidence | -0.106 |
| 10 | philpapers | commitment | commitment | nonbinary logit | -0.762 | commitment_defined | 0.065 |
| 11 | philpapers | nuance | nuance_defined | answer logit | -0.411 | nuance | -0.219 |
| 12 | ethics_commonsense | confidence | confidence | nonbinary logit | -0.833 | confidence | 0.341 |
| 13 | ethics_commonsense | commitment | commitment | nonbinary logit | -0.745 | commitment | 0.456 |
| 14 | ethics_commonsense | nuance | nuance_certainty | nonbinary logit | 0.751 | nuance_certainty | -0.638 |
| 15 | ethics_deontology | confidence | confidence | nonbinary logit | 0.332 | confidence | 0.253 |
| 16 | ethics_deontology | commitment | commitment_challenge | answer logit | 0.520 | commitment | -0.168 |
| 17 | ethics_deontology | nuance | nuance | binary entropy | 0.405 | nuance_ambiguity | -0.390 |
| 18 | ethics_justice | confidence | confidence | self challenge resistance | 0.339 | confidence | 0.228 |
| 19 | ethics_justice | commitment | commitment_challenge | nonbinary logit | -0.524 | commitment_challenge | 0.230 |
| 20 | ethics_justice | nuance | nuance_certainty | answer logit | -0.585 | nuance_certainty | -0.318 |
| 21 | ethics_virtue | confidence | confidence | binary entropy | -0.360 | confidence | 0.275 |
| 22 | ethics_virtue | commitment | commitment_challenge | nonbinary logit | -0.673 | commitment_challenge | 0.477 |
| 23 | ethics_virtue | nuance | nuance | nonbinary logit | 0.266 | nuance | 0.087 |
| 24 | ethics_utilitarianism | confidence | confidence | nonbinary logit | 0.390 | confidence | -0.040 |
| 25 | ethics_utilitarianism | commitment | commitment_challenge | binary entropy | -0.850 | commitment_defined | 0.367 |
| 26 | ethics_utilitarianism | nuance | nuance | answer logit | 0.520 | nuance | 0.250 |

## Figures

![all_datasets_matrix.png](figs/all_datasets_matrix.png)
![construct_matrix.png](figs/construct_matrix.png)
![gt_distributions.png](figs/gt_distributions.png)
![joint_ethics_commonsense.png](figs/joint_ethics_commonsense.png)
![joint_ethics_deontology.png](figs/joint_ethics_deontology.png)
![joint_ethics_justice.png](figs/joint_ethics_justice.png)
![joint_ethics_utilitarianism.png](figs/joint_ethics_utilitarianism.png)
![joint_ethics_virtue.png](figs/joint_ethics_virtue.png)
![joint_ontology_trivials.png](figs/joint_ontology_trivials.png)
![joint_philpapers.png](figs/joint_philpapers.png)
![joint_synonyms.png](figs/joint_synonyms.png)
![joint_triviaqa.png](figs/joint_triviaqa.png)
![matrix_ethics_commonsense.png](figs/matrix_ethics_commonsense.png)
![matrix_ethics_deontology.png](figs/matrix_ethics_deontology.png)
![matrix_ethics_justice.png](figs/matrix_ethics_justice.png)
![matrix_ethics_utilitarianism.png](figs/matrix_ethics_utilitarianism.png)
![matrix_ethics_virtue.png](figs/matrix_ethics_virtue.png)
![matrix_ontology_trivials.png](figs/matrix_ontology_trivials.png)
![matrix_philpapers.png](figs/matrix_philpapers.png)
![matrix_synonyms.png](figs/matrix_synonyms.png)
![matrix_triviaqa.png](figs/matrix_triviaqa.png)
![merged_construct_matrix.png](figs/merged_construct_matrix.png)
![merged_matrix.png](figs/merged_matrix.png)
![om_distributions.png](figs/om_distributions.png)
