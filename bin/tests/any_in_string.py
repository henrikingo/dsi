""" Add functionality like mock.ANY but partial matching a string """


# https://stackoverflow.com/questions/16976264/unittest-mock-asserting-partial-match-for-method-argument
# pylint: disable=invalid-name
class ANY_IN_STRING(str):
    """A helper object that compares equal to everything."""

    def __eq__(self, other):
        """ match ANY value contained in another """
        return self in other

    def __repr__(self):
        return '<ANY_IN>'
