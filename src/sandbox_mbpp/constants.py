# import builtins

# safe_builtins = {
#     name: getattr(builtins, name)
#     for name in [
#         'abs', 'all', 'any', 'bool', 'dict', 'enumerate',
#         'float', 'int', 'len', 'list', 'max', 'min',
#         'range', 'str', 'sum', 'tuple', 'zip', 'print',
#         'Exception', 'AssertionError', 'ValueError',
#         'TypeError', 'NameError', 'KeyError',
#         'IndexError', 'AttributeError',
#         'RuntimeError', 'SyntaxError',
#         'ZeroDivisionError',
#     ]
# }


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
