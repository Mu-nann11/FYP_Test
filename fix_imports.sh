#!/bin/bash
set -e

# Code/Segmentation/segmentation.py
sed -i 's/^from utils import/from Code.Utils.utils import/' Code/Segmentation/segmentation.py
sed -i 's/^from config import config/from Code.Config.config import config/' Code/Segmentation/segmentation.py

# Code/DataManagement/rename_file.py
sed -i 's/^from utils import/from Code.Utils.utils import/' Code/DataManagement/rename_file.py
sed -i 's/^from config import config/from Code.Config.config import config/' Code/DataManagement/rename_file.py

# Code/Pipeline/batch_run_all_to_one.py
sed -i 's/^from loader import/from Code.Utils.loader import/' Code/Pipeline/batch_run_all_to_one.py
sed -i 's/^from alignment import/from Code.Analysis.alignment import/' Code/Pipeline/batch_run_all_to_one.py
sed -i 's/^from segmentation import/from Code.Segmentation.segmentation import/' Code/Pipeline/batch_run_all_to_one.py
sed -i 's/^from features import/from Code.Analysis.features import/' Code/Pipeline/batch_run_all_to_one.py
sed -i 's/^from utils import/from Code.Utils.utils import/' Code/Pipeline/batch_run_all_to_one.py
sed -i 's/^from config import config/from Code.Config.config import config/' Code/Pipeline/batch_run_all_to_one.py

# Code/Pipeline/main.py
sed -i 's/^from crop_stitched_results import/from Code.Stitching.crop_stitched_results import/' Code/Pipeline/main.py

# Code/Analysis/features.py
sed -i 's/^from utils import/from Code.Utils.utils import/' Code/Analysis/features.py
sed -i 's/^from config import config/from Code.Config.config import config/' Code/Analysis/features.py

# Code/Analysis/ring_metrics_trial.py
sed -i 's/^from loader import/from Code.Utils.loader import/' Code/Analysis/ring_metrics_trial.py
sed -i 's/^from segmentation import/from Code.Segmentation.segmentation import/' Code/Analysis/ring_metrics_trial.py
sed -i 's/^from utils import/from Code.Utils.utils import/' Code/Analysis/ring_metrics_trial.py

# Code/Utils/loader.py (同目录引用也要加前缀)
sed -i 's/^from utils import/from Code.Utils.utils import/' Code/Utils/loader.py

echo "==> 修复完成！验证一下改动："
git diff --stat
