> ## Documentation Index
> Fetch the complete documentation index at: https://docs.fal.ai/llms.txt
> Use this file to discover all available pages before exploring further.

# Deploy to Production

> Deploy your models to production environments with confidence using the right deployment strategies and configurations. This guide focuses on model deployment patterns, authentication modes, and configuration best practices.

## Deployment Types

### Ephemeral Deployments

For development and testing, use ephemeral deployments with `fal run`.

```bash  theme={null}
fal run MyApp::path/to/myapp.py
```

By default, `fal run` uses `public` auth mode for easy testing. Use `--auth private` to require authentication:

```bash  theme={null}
fal run path/to/myapp.py::MyApp --auth private
```

Once you kill the `fal run` process in your terminal, the ephemeral deployment will be destroyed.

### Persistent Deployments

To permanently deploy your application or update/redeploy existing one, you can use the `fal deploy` command.

```bash  theme={null}
fal deploy path/to/myapp.py::MyApp --auth private
```

## Machine Types

You can specify the machine type of your app using the `machine_type` parameter in your `fal.App` class.

For GPU machines, you can also specify the number of GPUs you want to use with the `num_gpus` option.

```python  theme={null}
class MyApp(fal.App):
    machine_type = "GPU-A100"
    num_gpus = 1
    ...
```

Or you may specify the machine type in the `fal deploy` command.

```bash  theme={null}
fal deploy path/to/myapp.py::MyApp --machine-type GPU-A100 --num-gpus 1
```

### Machine Type Options

| Value     | Description                                      |
| :-------- | :----------------------------------------------- |
| XS        | 0.50 CPU cores, 512MB RAM                        |
| S         | 1 CPU core, 1GB RAM (default)                    |
| M         | 2 CPU cores, 2GB RAM                             |
| L         | 4 CPU cores, 15GB RAM                            |
| GPU-A6000 | 10 CPU cores, 18GB RAM, 1 GPU core (48GB VRAM)   |
| GPU-A100  | 12 CPU cores, 60GB RAM, 1 GPU core (40GB VRAM)   |
| GPU-H100  | 12 CPU cores, 112GB RAM, 1 GPU core (80GB VRAM)  |
| GPU-H200  | 12 CPU cores, 112GB RAM, 1 GPU core (141GB VRAM) |
| GPU-B200  | 24 CPU cores, 112GB RAM, 1 GPU core (192GB VRAM) |

### Multiple Machine Types

Allow your app to use multiple machine types for a larger pool of available machines:

```python  theme={null}
class MyApp(fal.App):
    machine_type = ["GPU-A100-40GB", "GPU-A100-80GB"]
```

## Rollout Strategies

Your app could be deployed using one of two strategies:

* `recreate`: default, instantly switch the app to the new revision.
* `rolling`: doesn't switch the app to the new one until there is at least 1 runner in the new revision.

You can specify the strategy using the `--strategy` flag, e.g.

```bash  theme={null}
fal deploy path/to/myapp.py::MyApp --strategy rolling
```

## Authentication Modes

Your app could be deployed in one of three authentication modes:

* `private`: default, your app is visible only to you and/or your team.
* `shared`: everyone can see and use your app, the caller pays for usage. This is how all of the apps in our [Model Gallery](https://fal.ai/models) work.
* `public`: everyone can see and use your app, the app owner (you) is paying for it.

Use `fal deploy`'s `--auth` flag or `fal.App`'s `app_auth` to specify your app's authentication mode, e.g.

```python  theme={null}
class MyApp(fal.App):
    auth_mode = "shared"
```

```bash  theme={null}
fal deploy path/to/myapp.py::MyApp --auth shared
```

To change the mode just redeploy the app.

## Best Practices

* **Choose rolling strategy** for production deployments to ensure zero downtime
* **Use appropriate authentication modes** based on your use case and cost considerations
* **Test thoroughly** with ephemeral deployments before permanent deployment
* **Monitor your deployments** using the fal dashboard and performance monitoring tools

## Managing Deployed Models

For managing your deployed models (listing, deleting, monitoring), see [Manage Deployments](/serverless/deployment-operations/manage-deployments/) and [Monitor Performance](/serverless/deployment-operations/monitor-performance/).
