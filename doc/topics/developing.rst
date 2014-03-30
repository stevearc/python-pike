Developing
==========

The fast way to get set up:

.. code-block:: bash

    wget https://raw.github.com/mathcamp/devbox/0.1.0/devbox/unbox.py && \
    python unbox.py git@github.com:stevearc/pike

The slow way to get set up:

.. code-block:: bash

    git clone git@github.com:stevearc/pike
    cd pike
    virtualenv pike_env
    . pike_env/bin/activate
    pip install -r requirements_dev.txt
    pip install -e .
    rm -r .git/hooks
    ln -s ../git_hooks .git/hooks # This will run pylint before you commit

You can run unit tests with:

.. code-block:: bash

    python setup.py nosetests

or:

.. code-block:: bash

    tox
