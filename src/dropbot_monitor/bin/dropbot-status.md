{% if not dropbot -%}
# No DropBot connected.
{%- else -%}
{% set properties = dropbot.properties -%}
# DropBot v{{ dropbot.hardware_version }}

 - **Firmware**: {{ properties.software_version }}
 - **Number of channels**: {{ dropbot.number_of_channels }}
 - **UUID**: {{ dropbot.uuid }}
{% if chip_inserted %}
**_Chip inserted._**
{%- else %}
**_No chip inserted._**
{%- endif %}
{%- endif %}
