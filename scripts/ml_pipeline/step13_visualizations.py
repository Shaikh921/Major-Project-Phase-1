import os
import json
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from sklearn.metrics import confusion_matrix, roc_curve, precision_recall_curve

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PLOTS_DIR = os.path.join(BASE_DIR, "plots")
os.makedirs(PLOTS_DIR, exist_ok=True)

HISTORY_PATH = os.path.join(BASE_DIR, "models", "training_history.json")
METRICS_PATH = os.path.join(BASE_DIR, "models", "evaluation_metrics.json")
PRED_PATH = os.path.join(BASE_DIR, "test_predictions.csv")

print("=" * 70)
print(" STEP 13: GENERATE HIGH-RESOLUTION MODEL VISUALIZATIONS ")
print("=" * 70)

# Load data
with open(HISTORY_PATH, "r") as f:
    history = json.load(f)
with open(METRICS_PATH, "r") as f:
    metrics = json.load(f)
pred_df = pd.read_csv(PRED_PATH)
pred_df["timestamp"] = pd.to_datetime(pred_df["timestamp"])

# 1. Training & Validation Loss Curve
plt.figure(figsize=(10, 5), dpi=150)
epochs = range(1, len(history["train_losses"]) + 1)
plt.plot(epochs, history["train_losses"], "b-o", linewidth=2, label="Training MSE Loss")
plt.plot(epochs, history["val_losses"], "r--s", linewidth=2, label="Validation MSE Loss")
plt.title("LSTM Autoencoder Training & Validation Loss vs Epochs", fontsize=14, fontweight="bold")
plt.xlabel("Epoch", fontsize=12)
plt.ylabel("Reconstruction Loss (MSE)", fontsize=12)
plt.grid(True, linestyle="--", alpha=0.6)
plt.legend(fontsize=11)
plt.tight_layout()
p1 = os.path.join(PLOTS_DIR, "1_loss_curves.png")
plt.savefig(p1)
plt.close()
print(f"[1] Saved Loss Curve to: {p1}")

# 2. ROC and Precision-Recall Curves
fpr, tpr, _ = roc_curve(pred_df["actual_label"], pred_df["reconstruction_error"])
precision, recall, _ = precision_recall_curve(pred_df["actual_label"], pred_df["reconstruction_error"])

fig, axes = plt.subplots(1, 2, figsize=(14, 5), dpi=150)

# ROC Curve
axes[0].plot(fpr, tpr, color="darkorange", lw=2, label=f"ROC Curve (AUC = {metrics['roc_auc']:.3f})")
axes[0].plot([0, 1], [0, 1], color="navy", lw=1.5, linestyle="--")
axes[0].set_xlim([0.0, 1.0])
axes[0].set_ylim([0.0, 1.05])
axes[0].set_xlabel("False Positive Rate (FPR)", fontsize=11)
axes[0].set_ylabel("True Positive Rate (Recall)", fontsize=11)
axes[0].set_title("Receiver Operating Characteristic (ROC)", fontsize=13, fontweight="bold")
axes[0].legend(loc="lower right", fontsize=10)
axes[0].grid(True, linestyle="--", alpha=0.6)

# PR Curve
axes[1].plot(recall, precision, color="teal", lw=2, label=f"PR Curve (AP = {metrics['pr_auc']:.3f})")
axes[1].axhline(y=np.mean(pred_df["actual_label"]), color="red", linestyle="--", label=f"Baseline Prevalance ({np.mean(pred_df['actual_label'])*100:.1f}%)")
axes[1].set_xlim([0.0, 1.0])
axes[1].set_ylim([0.0, 1.05])
axes[1].set_xlabel("Recall", fontsize=11)
axes[1].set_ylabel("Precision", fontsize=11)
axes[1].set_title("Precision-Recall (PR) Curve", fontsize=13, fontweight="bold")
axes[1].legend(loc="upper right", fontsize=10)
axes[1].grid(True, linestyle="--", alpha=0.6)

plt.tight_layout()
p2 = os.path.join(PLOTS_DIR, "2_roc_pr_curves.png")
plt.savefig(p2)
plt.close()
print(f"[2] Saved ROC and PR Curves to: {p2}")

# 3. Confusion Matrix at Operating Threshold
opt_th = metrics["optimal_threshold"]
cm = confusion_matrix(pred_df["actual_label"], (pred_df["reconstruction_error"] >= opt_th).astype(int))

fig, ax = plt.subplots(figsize=(6, 5), dpi=150)
cax = ax.matshow(cm, cmap="Blues", alpha=0.8)
for i in range(cm.shape[0]):
    for j in range(cm.shape[1]):
        ax.text(x=j, y=i, s=f"{cm[i, j]:,}", va="center", ha="center", size="xx-large", fontweight="bold")
fig.colorbar(cax)
ax.set_xticklabels(["", "Normal (0)", "Anomaly (1)"], fontsize=11)
ax.set_yticklabels(["", "Normal (0)", "Anomaly (1)"], fontsize=11)
plt.xlabel("Predicted Label", fontsize=12, labelpad=10)
plt.ylabel("Actual Label", fontsize=12)
plt.title(f"Confusion Matrix (Threshold = {opt_th:.3f})", fontsize=13, fontweight="bold", pad=20)
plt.tight_layout()
p3 = os.path.join(PLOTS_DIR, "3_confusion_matrix.png")
plt.savefig(p3)
plt.close()
print(f"[3] Saved Confusion Matrix to: {p3}")

# 4. Temporal Timeline of Detected Anomalies & Error Profile
plt.figure(figsize=(15, 6), dpi=150)
plt.plot(pred_df["timestamp"], pred_df["reconstruction_error"], color="black", lw=1, alpha=0.7, label="LSTM Reconstruction Error (MSE)")
plt.axhline(y=opt_th, color="red", linestyle="--", lw=2, label=f"Anomaly Threshold ({opt_th:.3f})")

# Highlight actual anomaly groundtruth windows
actual_anom = pred_df[pred_df["actual_label"] == 1]
plt.scatter(actual_anom["timestamp"], actual_anom["reconstruction_error"], color="crimson", s=15, alpha=0.8, label="Ground Truth Anomalies", zorder=3)

plt.yscale("log")
plt.title("Time-Series Anomaly Detection Timeline (Test Period)", fontsize=14, fontweight="bold")
plt.xlabel("Timestamp", fontsize=12)
plt.ylabel("Reconstruction Error MSE (Log Scale)", fontsize=12)
plt.legend(loc="upper right", fontsize=10)
plt.grid(True, linestyle="--", alpha=0.5)
plt.tight_layout()
p4 = os.path.join(PLOTS_DIR, "4_anomaly_timeline.png")
plt.savefig(p4)
plt.close()
print(f"[4] Saved Anomaly Timeline Plot to: {p4}")

print("\n" + "=" * 70)
print(" STEP 13 EXECUTION COMPLETE ")
print("=" * 70)
