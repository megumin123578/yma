from sqlalchemy import create_engine, inspect

engine = create_engine("sqlite:///./auth.db")
print(inspect(engine).get_table_names())