
def solution(arr):
    length = len(arr)
    if not length < 1: 
        removed_elemet = arr.pop()
        result = solution(arr) + removed_elemet
    else:
        result = 0
    return result

print(solution([1,2,3,4,5]))
print(solution([1,2,3,4,5,6]))