"""Run the same paper/independent checks after enabling root isolation."""
import importlib.util
import refine

refine.activate()
spec=importlib.util.spec_from_file_location('refined_contract_checks',refine.e.HERE/'verify.py')
module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
module.main()
