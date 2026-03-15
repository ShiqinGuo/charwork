def quick_sort(arr):
    if len(arr) <= 1:
        return arr

    import random
    pivot = arr[random.randrange(len(arr))]

    left_list = []
    mid_list = []
    right_list = []

    for num in arr:
        if num < pivot:
            left_list.append(num)
        elif num > pivot:
            right_list.append(num)
        else:
            mid_list.append(num)

    return quick_sort(left_list) + mid_list + quick_sort(right_list)


nums = [3, 6, 8, 10, 1, 2, 1]
sorted_nums = quick_sort(nums)
print(sorted_nums)
