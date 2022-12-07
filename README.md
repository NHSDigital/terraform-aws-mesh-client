# mesh-client-aws-serverless

Common code for MESH AWS serverless client, built to spec and tested by NHS Digital Solutions Assurance, using the

## Installation

Simply add the pre-built package to your python environment.

The latest version can be obtained with the following curl command if your system has it present:

```
package_version=$(curl -SL https://github.com/NHSDigital/mesh-client-aws-serverless/releases/latest | grep -Po 'Release v\K(\d+.\d+.\d+)' | head -n1)
```

Or you can set a specific version:

```
package_version="0.0.1"
```

Alternatively the main page of this repo will display the latest version i.e. 0.2.3, and previous versions can be searched, which you can substitute in place of `${package_version}` in the below commands.

### PIP

```
pip install https://github.com/NHSDigital/mesh-client-aws-serverless/releases/download/v${package_version}/mesh_client_aws_serverless-${package_version}-py3-none-any.whl
```

### requirements.txt

```
https://github.com/NHSDigital/mesh-client-aws-serverless/releases/download/v${package_version}/mesh_client_aws_serverless-${package_version}-py3-none-any.whl
```

### Poetry

```
poetry add https://github.com/NHSDigital/mesh-client-aws-serverless/releases/download/v${package_version}/mesh_client_aws_serverless-${package_version}-py3-none-any.whl
```

## Usage

TBC


