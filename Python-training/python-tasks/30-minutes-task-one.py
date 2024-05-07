def max_difference(arr):
    if len(arr) < 2:
        return -1

    min_element = arr[0]
    max_diff = -1 

    for i in range(1, len(arr)):
        if arr[i] > min_element:
            max_diff = max(max_diff, arr[i] - min_element)
        else:
            min_element = arr[i]

    return max_diff

arr = [2, 3, 10, 6, 4, 8, 1]
result = max_difference(arr)
print(result)  # 8
