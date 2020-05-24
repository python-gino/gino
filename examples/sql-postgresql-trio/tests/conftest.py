def pytest_addhooks(pluginmanager):
    pluginmanager.unregister(name="asyncio")
