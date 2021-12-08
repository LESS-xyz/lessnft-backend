def tron_function_selector(function_name, input_types):
    return f"{function_name}{input_types}".replace(" ", "").replace("'", "")
