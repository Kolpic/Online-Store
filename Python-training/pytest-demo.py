import pytest

def fun(x):
    return x +1

def func(x):
    return x * x

def test_fun():
    assert fun(3) == 4 

def test_func():
    assert func(5) == 25

def test_func_v2():
    assert func(5) == 25