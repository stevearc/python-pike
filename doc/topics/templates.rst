Templating Languages
====================

.. _jinja2:

Jinja2
------
If you are using a supported web framework, the instructions to get set up
should be :ref:`in that section <web_frameworks>`. That said, here are the bare
bones required to make jinja2 work:

.. code-block:: python

    pike_env = pike.Environment()
    jinja2_env.pike = pike_env
    jinja2_env.add_extension("pike.ext.JinjaExtension")

After doing that, you can use pike inside a template like so:

.. code-block:: jinja

    {% pike 'lib.js' %}
        <script type="text/javascript" src="{{ ASSET.url }}"></script>
    {% endpike %}

This block will be executed once for each item in the output of the 'lib.js'
graph. If it outputs multiple javascript files, they will all be referenced
inside of ``<script>`` tags.

By default, pike will use the default output of the graph. If you have a named
output, you can reference it by appending it to the graph name, separated by a
colon.

.. code-block:: jinja

    {% pike 'lib.coffee:map' %}
        <!-- coffeescript map file: {{ ASSET.url }} -->
    {% endpike %}

.. todo::
    Other templating language plugins?
