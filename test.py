def find_rect_num(n: int) -> int:
    """Return the nth rectangular number, which is n*(n+1)."""
    return n * (n + 1)






success = True
try:
    assert find_rect_num(4) == 20
    print("Passed test: 'assert find_rect_num(4) == 20'")
except AssertionError:
    print(f"Failed test: 'assert find_rect_num(4) == 20' got { find_rect_num(4) } instead")
    success = False

try:
    assert find_rect_num(5) == 30
    print("Passed test: 'assert find_rect_num(5) == 30'")
except AssertionError:
    print(f"Failed test: 'assert find_rect_num(5) == 30' got { find_rect_num(5) } instead")
    success = False

try:
    assert find_rect_num(6) == 42
    print("Passed test: 'assert find_rect_num(6) == 42'")
except AssertionError:
    print(f"Failed test: 'assert find_rect_num(6) == 42' got { find_rect_num(6) } instead")
    success = False

if success:
    final_answer("""def find_rect_num(n: int) -> int:
    """Return the nth rectangular number, which is n*(n+1)."""
    return n * (n + 1)


""")