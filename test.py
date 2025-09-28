from byterun import VirtualMachine

vm = VirtualMachine()

def test_addition(a, b):
    return a + b

def test_multiplication(x, y):
    return x * y

def test_subtract(x, y):
    return x - y

def test_division(x, y):
    return x / y

# Test cases
tests = [
    (test_addition, {'a': 2, 'b': 5}, 7),
    (test_multiplication, {'x': 3, 'y': 4}, 12),
    (test_subtract, {'x': 10, 'y': 3}, 7),
    (test_division, {'x': 10, 'y': 2}, 5),
]

for fn, args, expected in tests:
    code = fn.__code__
    try:
        result = vm.run_code(code, callargs=args, global_names=globals())
        print(f"{fn.__name__}({args}) = {result} (Expected: {expected})")
    except Exception as e:
        print(f"Error running {fn.__name__}: {e}")
