"""
Unit tests for Kubernetes manifests validation.
"""
import pytest
import yaml
import os
from pathlib import Path


# Get the k8s directory path
K8S_DIR = Path(__file__).parent.parent.parent / 'k8s'


class TestK8sManifests:
    """Test Kubernetes manifest validity."""
    
    def test_k8s_directory_exists(self):
        """Test that k8s directory exists."""
        assert K8S_DIR.exists(), f"K8s directory not found at {K8S_DIR}"
        assert K8S_DIR.is_dir()
    
    def test_namespace_yaml_valid(self):
        """Test namespace manifest is valid YAML."""
        namespace_file = K8S_DIR / 'namespace.yaml'
        assert namespace_file.exists()
        
        with open(namespace_file, 'r') as f:
            content = yaml.safe_load(f)
        
        assert content['apiVersion'] == 'v1'
        assert content['kind'] == 'Namespace'
        assert content['metadata']['name'] == 'ddfn-v2'
    
    def test_configmap_yaml_valid(self):
        """Test configmap manifest is valid YAML."""
        configmap_file = K8S_DIR / 'configmap.yaml'
        assert configmap_file.exists()
        
        with open(configmap_file, 'r') as f:
            content = yaml.safe_load(f)
        
        assert content['apiVersion'] == 'v1'
        assert content['kind'] == 'ConfigMap'
        assert content['metadata']['name'] == 'ddfn-config'
        assert 'data' in content
        assert 'DDFN_BROKER_HOST' in content['data']
    
    def test_secret_yaml_valid(self):
        """Test secret manifest is valid YAML."""
        secret_file = K8S_DIR / 'secret.yaml'
        assert secret_file.exists()
        
        with open(secret_file, 'r') as f:
            content = yaml.safe_load(f)
        
        assert content['apiVersion'] == 'v1'
        assert content['kind'] == 'Secret'
        assert content['metadata']['name'] == 'ddfn-secrets'
        assert content['type'] == 'Opaque'
    
    def test_broker_deployment_yaml_valid(self):
        """Test broker deployment manifest is valid YAML."""
        deployment_file = K8S_DIR / 'broker-deployment.yaml'
        assert deployment_file.exists()
        
        with open(deployment_file, 'r') as f:
            documents = list(yaml.safe_load_all(f))
        
        # Should have Deployment and Service
        assert len(documents) == 2
        
        deployment = documents[0]
        assert deployment['apiVersion'] == 'apps/v1'
        assert deployment['kind'] == 'Deployment'
        assert deployment['metadata']['name'] == 'broker'
        
        service = documents[1]
        assert service['apiVersion'] == 'v1'
        assert service['kind'] == 'Service'
        assert service['metadata']['name'] == 'broker'
    
    def test_fmp_deployment_yaml_valid(self):
        """Test FMP deployment manifest is valid YAML."""
        deployment_file = K8S_DIR / 'fmp-deployment.yaml'
        assert deployment_file.exists()
        
        with open(deployment_file, 'r') as f:
            documents = list(yaml.safe_load_all(f))
        
        # Should have multiple deployments and services
        assert len(documents) >= 2
        
        # Check first deployment
        deployment = documents[0]
        assert deployment['apiVersion'] == 'apps/v1'
        assert deployment['kind'] == 'Deployment'
        assert 'fmp' in deployment['metadata']['name']
    
    def test_airport_deployment_yaml_valid(self):
        """Test airport deployment manifest is valid YAML."""
        deployment_file = K8S_DIR / 'airport-deployment.yaml'
        assert deployment_file.exists()
        
        with open(deployment_file, 'r') as f:
            documents = list(yaml.safe_load_all(f))
        
        assert len(documents) >= 2
        
        deployment = documents[0]
        assert deployment['apiVersion'] == 'apps/v1'
        assert deployment['kind'] == 'Deployment'
        assert 'airport' in deployment['metadata']['name']
    
    def test_sim_manager_deployment_yaml_valid(self):
        """Test sim manager deployment manifest is valid YAML."""
        deployment_file = K8S_DIR / 'sim-manager-deployment.yaml'
        assert deployment_file.exists()
        
        with open(deployment_file, 'r') as f:
            documents = list(yaml.safe_load_all(f))
        
        assert len(documents) >= 2
        
        deployment = documents[0]
        assert deployment['apiVersion'] == 'apps/v1'
        assert deployment['kind'] == 'Deployment'
        assert 'sim-manager' in deployment['metadata']['name']
    
    def test_ingress_yaml_valid(self):
        """Test ingress manifest is valid YAML."""
        ingress_file = K8S_DIR / 'ingress.yaml'
        assert ingress_file.exists()
        
        with open(ingress_file, 'r') as f:
            documents = list(yaml.safe_load_all(f))
        
        # Should have Ingress and LoadBalancer Service
        assert len(documents) >= 1
        
        ingress = documents[0]
        assert ingress['apiVersion'] == 'networking.k8s.io/v1'
        assert ingress['kind'] == 'Ingress'
        assert 'ddfn' in ingress['metadata']['name']
    
    def test_kustomization_yaml_valid(self):
        """Test kustomization manifest is valid YAML."""
        kustomization_file = K8S_DIR / 'kustomization.yaml'
        assert kustomization_file.exists()
        
        with open(kustomization_file, 'r') as f:
            content = yaml.safe_load(f)
        
        assert content['apiVersion'] == 'kustomize.config.k8s.io/v1beta1'
        assert content['kind'] == 'Kustomization'
        assert 'resources' in content
        assert len(content['resources']) > 0


class TestK8sManifestContent:
    """Test Kubernetes manifest content requirements."""
    
    def test_all_deployments_have_probes(self):
        """Test that all deployments have liveness and readiness probes."""
        deployment_files = [
            K8S_DIR / 'broker-deployment.yaml',
            K8S_DIR / 'fmp-deployment.yaml',
            K8S_DIR / 'airport-deployment.yaml',
            K8S_DIR / 'sim-manager-deployment.yaml',
        ]
        
        for dep_file in deployment_files:
            if dep_file.exists():
                with open(dep_file, 'r') as f:
                    documents = list(yaml.safe_load_all(f))
                
                for doc in documents:
                    if doc and doc.get('kind') == 'Deployment':
                        containers = doc['spec']['template']['spec']['containers']
                        for container in containers:
                            assert 'livenessProbe' in container, \
                                f"Missing livenessProbe in {dep_file}"
                            assert 'readinessProbe' in container, \
                                f"Missing readinessProbe in {dep_file}"
    
    def test_all_deployments_have_resource_limits(self):
        """Test that all deployments have resource limits defined."""
        deployment_files = [
            K8S_DIR / 'broker-deployment.yaml',
            K8S_DIR / 'fmp-deployment.yaml',
            K8S_DIR / 'airport-deployment.yaml',
            K8S_DIR / 'sim-manager-deployment.yaml',
        ]
        
        for dep_file in deployment_files:
            if dep_file.exists():
                with open(dep_file, 'r') as f:
                    documents = list(yaml.safe_load_all(f))
                
                for doc in documents:
                    if doc and doc.get('kind') == 'Deployment':
                        containers = doc['spec']['template']['spec']['containers']
                        for container in containers:
                            assert 'resources' in container, \
                                f"Missing resources in {dep_file}"
                            assert 'limits' in container['resources'], \
                                f"Missing resource limits in {dep_file}"
                            assert 'requests' in container['resources'], \
                                f"Missing resource requests in {dep_file}"
    
    def test_health_check_endpoints_configured(self):
        """Test that health check endpoints are configured correctly."""
        deployment_files = [
            K8S_DIR / 'broker-deployment.yaml',
            K8S_DIR / 'fmp-deployment.yaml',
            K8S_DIR / 'airport-deployment.yaml',
            K8S_DIR / 'sim-manager-deployment.yaml',
        ]
        
        for dep_file in deployment_files:
            if dep_file.exists():
                with open(dep_file, 'r') as f:
                    documents = list(yaml.safe_load_all(f))
                
                for doc in documents:
                    if doc and doc.get('kind') == 'Deployment':
                        containers = doc['spec']['template']['spec']['containers']
                        for container in containers:
                            if 'livenessProbe' in container:
                                probe = container['livenessProbe']
                                assert probe.get('httpGet', {}).get('path') == '/health', \
                                    f"Health check path incorrect in {dep_file}"
