""" Exceptions used by pike """


class ValidationError(ValueError):

    """ Raised when some portion of a graph is invalid """
    pass


class StopProcessing(StopIteration):

    """ Raised to stop a graph mid-process. """
    pass
