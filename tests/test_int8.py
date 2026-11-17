import unittest

from reference.int8 import matmul_int8, wrap_int32


class Int8Tests(unittest.TestCase):
    def test_worked_example(self):
        self.assertEqual(
            matmul_int8([[1, -2, 3], [4, 0, -1]], [[2, 1], [-3, 2], [1, -4]]),
            [[11, -15], [7, 8]],
        )

    def test_all_int8_products(self):
        values = list(range(-128, 128))
        actual = matmul_int8([[value] for value in values], [values])
        for i, a in enumerate(values):
            for j, b in enumerate(values):
                self.assertEqual(actual[i][j], a * b)

    def test_accumulator_overflow(self):
        # 131072 * (-128 * -128) = 2**31, interpreted as -2**31.
        self.assertEqual(
            matmul_int8([[-128] * 131072], [[-128] for _ in range(131072)]),
            [[-(1 << 31)]],
        )
        self.assertEqual(wrap_int32(-(1 << 31) - 1), (1 << 31) - 1)

    def test_reject_invalid_inputs(self):
        invalid = [[], [[]], [[1], [1, 2]], [[128]], [[-129]], [[1.0]], [[True]], [1]]
        for matrix in invalid:
            with self.subTest(matrix=matrix):
                with self.assertRaises(ValueError):
                    matmul_int8(matrix, [[1]])
                with self.assertRaises(ValueError):
                    matmul_int8([[1]], matrix)
        with self.assertRaises(ValueError):
            matmul_int8([[1, 2]], [[1]])


if __name__ == "__main__":
    unittest.main()
