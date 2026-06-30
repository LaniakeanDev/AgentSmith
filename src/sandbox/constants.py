
DEFAULT_SERVER_PATH = 'src/fastmcp_server.py'

DEFAULT_SERVER_NAME = 'fastmcp_server.py'

DEFAULT_MCP_CMD = "python " + DEFAULT_SERVER_NAME

safe_builtins = {
    # === Type conversion ===
    'bool': bool,
    'int': int,
    'float': float,
    'str': str,
    'bytes': bytes,
    'bytearray': bytearray,
    'memoryview': memoryview,

    # === Collections ===
    'list': list,
    'tuple': tuple,
    'dict': dict,
    'set': set,
    'frozenset': frozenset,

    # === Iteration & Sequence operations ===
    'enumerate': enumerate,
    'range': range,
    'reversed': reversed,
    'slice': slice,
    'sorted': sorted,
    'iter': iter,
    'next': next,
    'len': len,
    'sum': sum,
    'min': min,
    'max': max,
    'all': all,
    'any': any,
    'zip': zip,
    'map': map,
    'filter': filter,

    # === Input/Output (safe) ===
    'print': print,
    'input': input,  # May be acceptable; remove if not
    'format': format,
    'repr': repr,
    'ascii': ascii,
    'ord': ord,
    'chr': chr,
    'bin': bin,
    'hex': hex,
    'oct': oct,

    # === Math operations ===
    'abs': abs,
    'divmod': divmod,
    'pow': pow,
    'round': round,
    'complex': complex,

    # === Object introspection (safe subset) ===
    'hasattr': hasattr,
    'getattr': getattr,
    'isinstance': isinstance,
    'issubclass': issubclass,
    'type': type,
    'id': id,
    'hash': hash,
    'dir': dir,  # Careful: can expose internals
    'callable': callable,
    'object': object,
    'property': property,
    'classmethod': classmethod,
    'staticmethod': staticmethod,
    'super': super,

    # === Common exceptions ===
    'Exception': Exception,
    'BaseException': BaseException,
    'SystemExit': SystemExit,
    'KeyboardInterrupt': KeyboardInterrupt,

    # === Standard exceptions ===
    'AssertionError': AssertionError,
    'AttributeError': AttributeError,
    'EOFError': EOFError,
    'ImportError': ImportError,
    'IndexError': IndexError,
    'KeyError': KeyError,
    'NameError': NameError,
    'RuntimeError': RuntimeError,
    'SyntaxError': SyntaxError,
    'TypeError': TypeError,
    'ValueError': ValueError,
    'ZeroDivisionError': ZeroDivisionError,
    'StopIteration': StopIteration,
    'StopAsyncIteration': StopAsyncIteration,
    'ArithmeticError': ArithmeticError,
    'FloatingPointError': FloatingPointError,
    'OverflowError': OverflowError,
    'MemoryError': MemoryError,
    'RecursionError': RecursionError,
    'LookupError': LookupError,
    'UnboundLocalError': UnboundLocalError,
    'NotImplementedError': NotImplementedError,

    # === Context managers ===
    'open': None,  # Explicitly blocked
    'file': None,  # Explicitly blocked

    # === Helpers ===
    'help': None,  # Blocked - can be interactive
    'vars': vars,  # Careful: exposes __dict__
    'locals': None,  # Blocked - exposes sandbox internals
    'globals': None,  # Blocked - exposes sandbox internals

    # === Code execution (blocked) ===
    'eval': None,
    'exec': None,
    'compile': None,
    '__import__': None,
    'execfile': None,  # Python 2, but block anyway
    'reload': None,  # Python 2, but block anyway

    # === Attribute access ===
    '__dict__': None,  # Block direct access
    '__class__': None,  # Block direct access
    '__bases__': None,  # Block direct access
    '__mro__': None,  # Block direct access
    '__subclasses__': None,  # Block direct access
    '__globals__': None,  # Block direct access

    # === Module loading ===
    '__loader__': None,
    '__spec__': None,
    '__package__': None,

    # === OS/System (blocked) ===
    'exit': None,
    'quit': None,

    # === Advanced (optional - add if needed) ===
    'any': any,
    'all': all,
    'sorted': sorted,
    'reversed': reversed,
    'enumerate': enumerate,
    'zip': zip,
    'map': map,
    'filter': filter,
    'reduce': None,  # Not a built-in in Python 3 (in functools)

    # === Datetime (safe) ===
    # Not builtins - import through safe modules
}