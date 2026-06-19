safe_builtins = {
    'abs': abs, 'all': all, 'any': any, 'bool': bool,
    'dict': dict, 'enumerate': enumerate, 'float': float,
    'int': int, 'len': len, 'list': list, 'max': max,
    'min': min, 'range': range, 'str': str, 'sum': sum,
    'tuple': tuple, 'zip': zip, 'print': print,
    'Exception': Exception,
    'AssertionError': AssertionError,
    'ValueError': ValueError,
    'TypeError': TypeError,
    'NameError': NameError,
    'KeyError': KeyError,
    'IndexError': IndexError,
    'AttributeError': AttributeError,
    'RuntimeError': RuntimeError,
    'SyntaxError': SyntaxError,
    'ZeroDivisionError': ZeroDivisionError,
    # Deliberately exclude: open, eval, exec, __import__
}
