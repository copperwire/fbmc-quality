import os
from pathlib import Path

from fbmc_quality.dataframe_schemas.cache_db.cache_db_functions import store_df_in_table


def create_default_folder(default_folder_path: Path):
    try:
        default_folder_path.mkdir(parents=True, exist_ok=True)
    except Exception as e:
        raise FileExistsError(f"Error creating default folder: {e}") from e


path_to_db = os.getenv("DB_PATH")

if path_to_db is None:
    default_folder_path = Path.home() / Path(".flowbased_data")
    create_default_folder(default_folder_path)
    path_to_db = default_folder_path / "linearisation_analysis.duckdb"
else:
    if not path_to_db.endswith("db"):
        raise EnvironmentError("Misconfigured env-var, DB_PATH must end with 'db' or 'duckdb'")

    path_to_db = Path(path_to_db)
    if not path_to_db.parent.exists():
        raise FileNotFoundError(f"No folder named {path_to_db.parent}")

DB_PATH = path_to_db
