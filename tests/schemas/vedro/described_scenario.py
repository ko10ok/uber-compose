from d42 import schema

DescribedScenario = schema.dict({
    'name': schema.str,
    'skipped': schema.bool,
    'env': schema.any,
    "env_desc": schema.any,
    'description': schema.str,
})

DescribedScenarios = schema.list(DescribedScenario)
