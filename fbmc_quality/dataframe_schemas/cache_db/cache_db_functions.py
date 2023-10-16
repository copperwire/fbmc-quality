
import pandas
from sqlalchemy import Engine, text


def store_df_in_table(table_name: str, df: pandas.DataFrame, engine: Engine):
    # Convert the DataFrame to a list of dictionaries
    data_list = df.to_dict(orient='records')

    # Generate the column names and placeholders dynamically
    columns = ', '.join(df.columns)
    placeholders = ', '.join(f':{col}' for col in df.columns)

    # Define the dynamic SQL statement for "INSERT OR REPLACE INTO"
    insert_sql = text(f'''
        INSERT OR REPLACE INTO {table_name} ({columns})
        VALUES ({placeholders})
    ''')

    with engine.connect() as connection:
        connection.execute(insert_sql, data_list)
        connection.commit()
