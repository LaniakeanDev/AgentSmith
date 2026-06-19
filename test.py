def find_rect_num(n):
    return n * (n + 1)


try:
    assert find_rect_num(4) == 20
    print("Passed test: 'assert find_rect_num(4) == 20'")
except AssertionError:
    print(f"Failed test: 'assert find_rect_num(4) == 20' got \
          {find_rect_num(4)} instead")
