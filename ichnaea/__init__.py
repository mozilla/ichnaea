# Disable deprecation warnings in production mode
import warnings

warnings.simplefilter("ignore", DeprecationWarning)
warnings.simplefilter("ignore", PendingDeprecationWarning)
