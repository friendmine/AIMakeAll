"""Signed INT8 GEMM with two's-complement INT32 wrapping."""


def wrap_int32(value: int) -> int:
    """Interpret the low 32 bits as a signed integer."""
    return ((value + (1 << 31)) % (1 << 32)) - (1 << 31)


def _shape(matrix: list[list[int]], name: str) -> tuple[int, int]:
    if not isinstance(matrix, list) or not matrix:
        raise ValueError(f"{name} must be a non-empty list of rows")
    if not isinstance(matrix[0], list) or not matrix[0]:
        raise ValueError(f"{name} rows must be non-empty lists")
    columns = len(matrix[0])
    for row in matrix:
        if not isinstance(row, list) or len(row) != columns:
            raise ValueError(f"{name} must be rectangular")
        if any(type(value) is not int or not -128 <= value <= 127 for value in row):
            raise ValueError(f"{name} values must be integers in [-128, 127]")
    return len(matrix), columns


def matmul_int8(a: list[list[int]], b: list[list[int]]) -> list[list[int]]:
    """Compute A[M,K] @ B[K,N]; reject empty, ragged or non-INT8 input."""
    m, k = _shape(a, "A")
    b_rows, n = _shape(b, "B")
    if k != b_rows:
        raise ValueError("A columns must equal B rows")
    return [
        [wrap_int32(sum(a[i][p] * b[p][j] for p in range(k))) for j in range(n)]
        for i in range(m)
    ]


if __name__ == "__main__":
    a = [[1, -2, 3], [4, 0, -1]]
    b = [[2, 1], [-3, 2], [1, -4]]
    print("A =", a)
    print("B =", b)
    print("C =", matmul_int8(a, b))
