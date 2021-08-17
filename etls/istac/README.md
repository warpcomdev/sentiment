# Istac ETL

This ETL collects information from Istac public API to update KeyPerformanceIndicator entities in Thinking Cities platform.
~
## Installation

This script requires python3 3.7 or higher, and depends on several libraries that are enumerated in the [requirements.txt](requirements.txt) file. It is recommended to create a `virtualenv` for the script, and install all the dependencies there:

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

To run the script, make sure the virtualenv is activated, and run `collect.py` with the proper parameters or configuration file (see next section).

## Configuration

The ETL uses the following configuration variables, that can be passwd in either as command line flags, environment variables, or inside an `.ini` config file:

 - `-c CONFIG`, `--config CONFIG` (env `CONFIG_FILE`): config file path
- `--keystone-url` (env `KEYSTONE_URL`): Keystone URL
- `--orion-url` (env `ORION_URL`): Orion URL
- `--orion-service` (env `ORION_SERVICE`): Orion service name
- `--orion-subservice` (env `ORION_SUBSERVICE`): Orion subservice name
- `--orion-username` (env `ORION_USERNAME`): Orion username
- `--orion-password` (env `ORION_PASSWORD`): Orion password
- `--istac-year` (env `ISTAC_YEAR`): Year to collect info for.

Example of `.ini` config file in [istac.ini.sample](istac.ini.sample)

## Behaviour

The ETL performs the following tasks:

- Connects and authenticates to Keystone API.
- Discovers all the available indicators and geographical granularities in the Istac API.
- Maps each indicator and granularity to a KeyPerformanceIndicator `entityID`, with the following format: `{indicator_code}:{geographical_granularity}:YEARLY:ABSOLUTE`.

The ETL batches updates to different `KeyPerformanceIndicators`s, to make it more efficient.

## Attributes

This is the mapping between Istac's indicators and granularities, and `KeyPerformanceIndicators` entity attributes:

- the `EntityID` of the `KeyPerformanceIndicator` is built from the indicator code and geographic granularity like this: `{indicator_code}:{geographical_granularity}:YEARLY:ABSOLUTE`.
- The `source` of the Entity comes from the indicator `code`.
- The `product` of the Entity comes from the indicator geography dimension.
- The `name` of the Entity comes from the indicator's title.
- The `description` of the Entity comes from the indicator's description.
- The `aggregatedData` of the Entity defines the geographical granularity.
