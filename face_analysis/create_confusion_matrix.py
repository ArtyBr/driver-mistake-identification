"""
Create custom confusion matrices from manually entered data.

Usage:
    python create_confusion_matrix.py

You'll be prompted to enter the matrix values row by row.
"""

import argparse
import numpy as np
import matplotlib.pyplot as plt
from sklearn.metrics import ConfusionMatrixDisplay


DEFAULT_LABELS = ['Left Mirror', 'Right Mirror', 'Looking Ahead', 'Rear Mirror']


def input_matrix(name, labels):
    n = len(labels)
    print(f"\nEnter {name} confusion matrix ({n}x{n})")
    print(f"Rows = true labels, Columns = predicted labels")
    print(f"Labels: {labels}")
    print(f"Enter each row as space-separated integers:\n")

    matrix = []
    for i, label in enumerate(labels):
        while True:
            row_str = input(f"  {label} → ")
            vals = row_str.strip().split()
            if len(vals) == n:
                try:
                    matrix.append([int(v) for v in vals])
                    break
                except ValueError:
                    print(f"  Invalid input. Enter {n} integers.")
            else:
                print(f"  Expected {n} values, got {len(vals)}. Try again.")

    return np.array(matrix)


def compute_metrics(cm, labels):
    """Compute per-class and macro metrics from a confusion matrix."""
    n = len(labels)
    precision = np.zeros(n)
    recall = np.zeros(n)
    f1 = np.zeros(n)
    support = cm.sum(axis=1)

    for i in range(n):
        tp = cm[i, i]
        fp = cm[:, i].sum() - tp
        fn = cm[i, :].sum() - tp
        precision[i] = tp / (tp + fp) if (tp + fp) > 0 else 0
        recall[i] = tp / (tp + fn) if (tp + fn) > 0 else 0
        f1[i] = 2 * precision[i] * recall[i] / (precision[i] + recall[i]) if (precision[i] + recall[i]) > 0 else 0

    accuracy = np.trace(cm) / cm.sum()
    macro_p = precision.mean()
    macro_r = recall.mean()
    macro_f1 = f1.mean()

    print(f"\n  {'Class':<15} {'Precision':>9} {'Recall':>9} {'F1':>9} {'Support':>9}")
    print(f"  {'-'*52}")
    for i, label in enumerate(labels):
        print(f"  {label:<15} {precision[i]:>9.3f} {recall[i]:>9.3f} {f1[i]:>9.3f} {support[i]:>9d}")
    print(f"  {'-'*52}")
    print(f"  {'Accuracy':<15} {'':>9} {'':>9} {accuracy:>9.3f} {cm.sum():>9d}")
    print(f"  {'Macro avg':<15} {macro_p:>9.3f} {macro_r:>9.3f} {macro_f1:>9.3f} {cm.sum():>9d}")


def main():
    parser = argparse.ArgumentParser(description="Create custom confusion matrices")
    parser.add_argument("--labels", nargs='+', default=DEFAULT_LABELS,
                        help="Class labels")
    parser.add_argument("--output", type=str, default="custom_confusion_matrices.png",
                        help="Output image path")
    parser.add_argument("--single", action='store_true',
                        help="Only create one confusion matrix (not a comparison)")
    parser.add_argument("--title1", type=str, default="SVM", help="Title for first matrix")
    parser.add_argument("--title2", type=str, default="KMeans", help="Title for second matrix")
    parser.add_argument("--cmap1", type=str, default="Blues", help="Colormap for first matrix")
    parser.add_argument("--cmap2", type=str, default="Oranges", help="Colormap for second matrix")
    args = parser.parse_args()

    labels = args.labels

    cm1 = input_matrix(args.title1, labels)
    print(f"\n{args.title1} metrics:")
    compute_metrics(cm1, labels)

    if args.single:
        fig, ax = plt.subplots(1, 1, figsize=(8, 6))
        ConfusionMatrixDisplay(cm1, display_labels=labels).plot(
            ax=ax, cmap=args.cmap1, values_format='d', xticks_rotation=45
        )
        ax.set_title(f'{args.title1} Confusion Matrix')
    else:
        cm2 = input_matrix(args.title2, labels)
        print(f"\n{args.title2} metrics:")
        compute_metrics(cm2, labels)

        fig, axes = plt.subplots(1, 2, figsize=(16, 6))
        ConfusionMatrixDisplay(cm1, display_labels=labels).plot(
            ax=axes[0], cmap=args.cmap1, values_format='d', xticks_rotation=45
        )
        axes[0].set_title(f'{args.title1} Confusion Matrix')

        ConfusionMatrixDisplay(cm2, display_labels=labels).plot(
            ax=axes[1], cmap=args.cmap2, values_format='d', xticks_rotation=45
        )
        axes[1].set_title(f'{args.title2} Confusion Matrix')

    plt.tight_layout()
    plt.savefig(args.output, dpi=150, bbox_inches='tight')
    print(f"\nSaved to {args.output}")
    plt.close()


if __name__ == "__main__":
    main()
