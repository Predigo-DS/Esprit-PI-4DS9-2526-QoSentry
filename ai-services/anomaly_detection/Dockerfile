FROM pytorch/pytorch:2.8.0-cuda12.8-cudnn9-runtime
WORKDIR /app

# Install Jupyter and dependencies
RUN apt-get update && apt-get install -y curl && rm -rf /var/lib/apt/lists/*

# Install requirements
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Install Jupyter
RUN pip install --no-cache-dir jupyter notebook

# Copy application code
COPY app/ ./app/
COPY train/ ./train/

# Expose Jupyter port
EXPOSE 8888

# Run Jupyter Notebook
CMD ["jupyter", "notebook", "--ip=0.0.0.0", "--port=8888", "--no-browser", "--allow-root", "--NotebookApp.token=''"]