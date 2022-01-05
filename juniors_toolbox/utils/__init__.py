JSYSTEM_PADDING_TEXT = "This is padding data to alignment....."

# pylint: disable=invalid-name
class classproperty(property):
    def __get__(self, cls, owner):
        return classmethod(self.fget).__get__(None, owner)()
# pylint: enable=invalid-name

clamp = lambda x, min, max: min if x < min else max if x > max else x
clamp01 = lambda x: clamp(x, 0, 1)
sign = lambda x: 1 if x >= 0 else -1