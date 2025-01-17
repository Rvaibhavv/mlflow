from tensorflow import keras

from mlflow import log_metrics, log_params, log_text
from mlflow.utils.autologging_utils import ExceptionSafeClass


class MLflowCallback(keras.callbacks.Callback, metaclass=ExceptionSafeClass):
    """Callback for logging Tensorflow training metrics to MLflow.

    This callback logs model information at training start, and logs training metrics every epoch or
    every n steps (defined by the user) to MLflow.

    Args:
        log_every_epoch: bool, If True, log metrics every epoch. If False, log metrics every n
            steps.
        log_every_n_steps: int, log metrics every n steps. If None, log metrics every epoch.
            Must be `None` if `log_every_epoch=True`.

    .. code-block:: python
        :caption: Example

        from tensorflow import keras
        import mlflow
        import numpy as np

        # Prepare data for a 2-class classification.
        data = tf.random.uniform([8, 28, 28, 3])
        label = tf.convert_to_tensor(np.random.randint(2, size=8))

        model = keras.Sequential(
            [
                keras.Input([28, 28, 3]),
                keras.layers.Flatten(),
                keras.layers.Dense(2),
            ]
        )

        model.compile(
            loss=keras.losses.SparseCategoricalCrossentropy(from_logits=True),
            optimizer=keras.optimizers.Adam(0.001),
            metrics=[keras.metrics.SparseCategoricalAccuracy()],
        )

        with mlflow.start_run() as run:
            model.fit(
                data,
                label,
                batch_size=4,
                epochs=2,
                callbacks=[MLflowCallback(run)],
            )
    """

    def __init__(self, log_every_epoch=True, log_every_n_steps=None):
        self.log_every_epoch = log_every_epoch
        self.log_every_n_steps = log_every_n_steps

        if log_every_epoch and log_every_n_steps is not None:
            raise ValueError(
                "`log_every_n_steps` must be None if `log_every_epoch=True`, received "
                f"`log_every_epoch={log_every_epoch}` and `log_every_n_steps={log_every_n_steps}`."
            )
        if not log_every_epoch and log_every_n_steps is None:
            raise ValueError(
                "`log_every_n_steps` must be specified if `log_every_epoch=False`, received"
                "`log_every_n_steps=False` and `log_every_n_steps=None`."
            )

    def on_train_begin(self, logs=None):
        """Log model architecture and optimizer configuration when training begins."""
        config = self.model.optimizer.get_config()
        log_params({f"opt_{k}": v for k, v in config.items()})

        model_summary = []

        def print_fn(line, *args, **kwargs):
            model_summary.append(line)

        self.model.summary(print_fn=print_fn)
        summary = "\n".join(model_summary)
        log_text(summary, artifact_file="model_summary.txt")

    def on_epoch_end(self, epoch, logs=None):
        """Log metrics at the end of each epoch."""
        if not self.log_every_epoch or logs is None:
            return
        log_metrics(logs, step=epoch, synchronous=False)

    def on_batch_end(self, batch, logs=None):
        """Log metrics at the end of each batch with user specified frequency."""
        if self.log_every_n_steps is None or logs is None:
            return
        current_iteration = int(self.model.optimizer.iterations.numpy())

        if current_iteration % self.log_every_n_steps == 0:
            log_metrics(logs, step=current_iteration, synchronous=False)

    def on_test_end(self, logs=None):
        """Log validation metrics at validation end."""
        if logs is None:
            return
        metrics = {"validation_" + k: v for k, v in logs.items()}
        log_metrics(metrics, synchronous=False)
