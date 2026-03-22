import pandas as pd

df = pd.read_csv("A4_cell_features.csv")

# 列名已更新：features.py 输出 *_nuc_mean 格式
ER_thresh  = df["ER_nuc_mean"].mean()  + 3 * df["ER_nuc_mean"].std()
PR_thresh  = df["PR_nuc_mean"].mean()  + 3 * df["PR_nuc_mean"].std()
HER2_thresh = df["HER2_nuc_mean"].mean()  # 或者按 HER2 scoring 规则
Ki67_thresh = df["KI67_nuc_mean"].quantile(0.8)  # 比如前 20% 当高增殖

df["ER_label"]   = (df["ER_nuc_mean"]   > ER_thresh).astype(int)
df["PR_label"]   = (df["PR_nuc_mean"]   > PR_thresh).astype(int)
df["HER2_label"] = (df["HER2_nuc_mean"] > HER2_thresh).astype(int)
df["Ki67_label"] = (df["KI67_nuc_mean"] > Ki67_thresh).astype(int)

df.to_csv("A4_cell_features_labeled.csv", index=False)
