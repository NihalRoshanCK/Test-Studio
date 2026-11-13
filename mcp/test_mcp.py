"""Offline checks for the MCP server helpers: python apps/test_studio/mcp/test_mcp.py"""
import json
import unittest

import test_studio_mcp as m


class TestMcpHelpers(unittest.TestCase):
	def test_clean_steps(self):
		out = m.clean_steps([{"action": "set_field", "selector": "Customer", "value": "{{customer}}", "junk": 1},
		                     {"action": "run_snippet", "snippet": "Order", "inputs": {"discount": 8}}])
		self.assertEqual(out[0], {"action": "set_field", "selector": "Customer", "value": "{{customer}}"})
		self.assertEqual(json.loads(out[1]["value"]), {"discount": "8"})
		with self.assertRaises(ValueError):
			m.clean_steps([{"action": "explode"}])
		with self.assertRaises(ValueError):
			m.clean_steps([{"action": "run_snippet"}])

	def test_sentence(self):
		self.assertEqual(m.sentence({"action": "set_field", "selector": "Customer", "value": "C-1"}), "Set Customer to C-1")
		self.assertEqual(m.sentence({"action": "run_snippet", "snippet": "Order", "value": '{"discount": "8"}'}), "Run snippet 'Order' with discount=8")


if __name__ == "__main__":
	unittest.main()
