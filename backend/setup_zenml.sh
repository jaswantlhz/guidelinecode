#!/bin/bash

# Exit on error
set -e

echo "🚀 Initializing ZenML repository..."
zenml init

echo "🔌 Installing ZenML MLflow integration..."
zenml integration install mlflow -y

echo "🧪 Registering MLflow experiment tracker..."
# Check if it already exists to avoid errors on re-run
if zenml experiment-tracker describe mlflow_tracker > /dev/null 2>&1; then
    echo "MLflow tracker already exists."
else
    zenml experiment-tracker register mlflow_tracker --flavor=mlflow
fi

echo "📚 Registering a new stack with the MLflow tracker..."
if zenml stack describe local_mlflow_stack > /dev/null 2>&1; then
    echo "Stack 'local_mlflow_stack' already exists. Setting as active..."
    zenml stack set local_mlflow_stack
else
    zenml stack register local_mlflow_stack -a default -o default -e mlflow_tracker --set
fi

echo "✅ ZenML & MLflow setup complete!"
echo "Run 'mlflow ui' in a separate terminal to view the dashboard."
