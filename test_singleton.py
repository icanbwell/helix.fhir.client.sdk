#!/usr/bin/env python3
"""
Test script to verify the FhirClient singleton implementation
"""
import threading
import time
from helix_fhir_client_sdk.fhir_client import FhirClient


def test_singleton_basic():
    """Test basic singleton behavior"""
    print("Testing basic singleton behavior...")
    
    # Create two instances
    client1 = FhirClient()
    client2 = FhirClient()
    
    # They should be the same object
    assert client1 is client2, "FhirClient instances should be identical"
    assert id(client1) == id(client2), "FhirClient instances should have the same memory address"
    
    print("✓ Basic singleton test passed")


def test_singleton_thread_safety():
    """Test singleton behavior across multiple threads"""
    print("Testing thread safety...")
    
    instances = []
    
    def create_instance():
        """Function to create instance in a thread"""
        client = FhirClient()
        instances.append(client)
        time.sleep(0.1)  # Small delay to increase chance of race condition
    
    # Create multiple threads
    threads = []
    for i in range(10):
        thread = threading.Thread(target=create_instance)
        threads.append(thread)
    
    # Start all threads
    for thread in threads:
        thread.start()
    
    # Wait for all threads to complete
    for thread in threads:
        thread.join()
    
    # All instances should be the same
    first_instance = instances[0]
    for instance in instances:
        assert instance is first_instance, "All instances should be identical across threads"
    
    print(f"✓ Thread safety test passed with {len(instances)} instances all being identical")


def test_singleton_with_configuration():
    """Test that singleton maintains configuration across different references"""
    print("Testing configuration persistence...")
    
    # Get first reference and configure it
    client1 = FhirClient()
    client1.url("http://test-server.com").resource("Patient").page_size(50)
    
    # Get second reference
    client2 = FhirClient()
    
    # Configuration should be the same
    assert client1._url == client2._url, "URL should be the same across references"
    assert client1._resource == client2._resource, "Resource should be the same across references"
    assert client1._page_size == client2._page_size, "Page size should be the same across references"
    
    print("✓ Configuration persistence test passed")


def test_clone_method():
    """Test that clone method resets state but returns same instance"""
    print("Testing clone method...")
    
    # Configure instance
    client1 = FhirClient()
    client1.url("http://test-server.com").resource("Patient").page_size(50)
    original_url = client1._url
    
    # Clone should return same instance but reset state
    client2 = client1.clone()
    
    # Should be same instance
    assert client1 is client2, "Clone should return the same instance"
    
    # State should be reset
    assert client2._url is None, "URL should be reset after clone"
    assert client2._resource is None, "Resource should be reset after clone"
    assert client2._page_size is None, "Page size should be reset after clone"
    
    print("✓ Clone method test passed")


def test_reset_singleton():
    """Test the reset_singleton class method"""
    print("Testing reset_singleton method...")
    
    # Create an instance
    client1 = FhirClient()
    client1.url("http://test-server.com")
    
    # Reset the singleton
    FhirClient.reset_singleton()
    
    # Next instance should be a fresh one
    client2 = FhirClient()
    
    # Should be different instances now
    assert client1 is not client2, "After reset, new instance should be different"
    assert client2._url is None, "New instance should have default state"
    
    print("✓ Reset singleton test passed")


if __name__ == "__main__":
    print("Running FhirClient Singleton Tests...\n")
    
    try:
        test_singleton_basic()
        test_singleton_thread_safety()
        test_singleton_with_configuration()
        test_clone_method()
        test_reset_singleton()
        
        print("\n🎉 All tests passed! FhirClient singleton implementation is working correctly.")
        
    except Exception as e:
        print(f"\n❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
