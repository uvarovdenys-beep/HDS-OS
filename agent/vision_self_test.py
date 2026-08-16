#!/usr/bin/env python3
"""
HDS Vision Self-Test Suite
Tests AI vision daemon with actual screen captures and analysis
"""

import os
import json
import time
import requests
from pathlib import Path

class VisionSelfTest:
    def __init__(self, port=9001):
        self.port = port
        self.api_url = f"http://localhost:{port}"
        self.results = {
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
            "tests": [],
            "passed": 0,
            "failed": 0
        }

    def test_health(self):
        """Test daemon health"""
        print("🧪 Test 1: Health Check")
        try:
            resp = requests.get(f"{self.api_url}/health", timeout=5)
            if resp.status_code == 200:
                print("   ✅ Vision daemon is healthy")
                self.log_test("health_check", True)
                return True
            else:
                print(f"   ❌ Health check failed: {resp.status_code}")
                self.log_test("health_check", False)
                return False
        except Exception as e:
            print(f"   ❌ Connection error: {e}")
            self.log_test("health_check", False)
            return False

    def test_capture_screen(self):
        """Test screen capture"""
        print("🧪 Test 2: Screen Capture")
        try:
            payload = {"type": "capture_screen"}
            resp = requests.post(
                f"{self.api_url}/execute",
                json=payload,
                timeout=10,
                headers={"Content-Type": "application/json"}
            )
            
            if resp.status_code == 200:
                data = resp.json()
                if data.get("success"):
                    filename = data.get("filename", "unknown")
                    width = data.get("width", 0)
                    height = data.get("height", 0)
                    print(f"   ✅ Screen captured: {width}x{height} ({filename})")
                    self.log_test("screen_capture", True, data)
                    return True
                else:
                    print(f"   ❌ Capture failed: {data.get('error')}")
                    self.log_test("screen_capture", False, data)
                    return False
            else:
                print(f"   ❌ Request failed: {resp.status_code}")
                self.log_test("screen_capture", False)
                return False
        except Exception as e:
            print(f"   ❌ Error: {e}")
            self.log_test("screen_capture", False)
            return False

    def test_analyze_image(self):
        """Test image analysis"""
        print("🧪 Test 3: Image Analysis (OCR)")
        try:
            # First capture, then analyze
            payload = {"type": "analyze_image"}
            resp = requests.post(
                f"{self.api_url}/execute",
                json=payload,
                timeout=15,
                headers={"Content-Type": "application/json"}
            )
            
            if resp.status_code == 200:
                data = resp.json()
                if data.get("success"):
                    text = data.get("text_content", "")[:50] + "..."
                    objects = data.get("detected_objects", [])
                    confidence = data.get("confidence", 0)
                    print(f"   ✅ Analysis complete")
                    print(f"      • Detected text: {text if text else '(none)'}")
                    print(f"      • Objects found: {len(objects)}")
                    print(f"      • Confidence: {confidence}%")
                    self.log_test("image_analysis", True, data)
                    return True
                else:
                    print(f"   ❌ Analysis failed: {data.get('error')}")
                    self.log_test("image_analysis", False)
                    return False
            else:
                print(f"   ❌ Request failed: {resp.status_code}")
                self.log_test("image_analysis", False)
                return False
        except Exception as e:
            print(f"   ❌ Error: {e}")
            self.log_test("image_analysis", False)
            return False

    def test_element_detection(self):
        """Test UI element detection"""
        print("🧪 Test 4: Element Detection")
        try:
            payload = {"type": "detect_elements"}
            resp = requests.post(
                f"{self.api_url}/execute",
                json=payload,
                timeout=10,
                headers={"Content-Type": "application/json"}
            )
            
            if resp.status_code == 200:
                data = resp.json()
                if data.get("success"):
                    elements = data.get("elements", [])
                    print(f"   ✅ Detected {len(elements)} UI elements")
                    for elem in elements[:3]:  # Show first 3
                        elem_type = elem.get("type", "unknown")
                        bbox = elem.get("bbox_relative", [0, 0, 0, 0])
                        print(f"      • {elem_type}: bbox {bbox}")
                    if len(elements) > 3:
                        print(f"      ... and {len(elements)-3} more")
                    self.log_test("element_detection", True, data)
                    return True
                else:
                    print(f"   ❌ Detection failed: {data.get('error')}")
                    self.log_test("element_detection", False)
                    return False
            else:
                print(f"   ❌ Request failed: {resp.status_code}")
                self.log_test("element_detection", False)
                return False
        except Exception as e:
            print(f"   ❌ Error: {e}")
            self.log_test("element_detection", False)
            return False

    def test_api_response_time(self):
        """Test API response time"""
        print("🧪 Test 5: Performance (Response Time)")
        try:
            start = time.time()
            resp = requests.post(
                f"{self.api_url}/execute",
                json={"type": "capture_screen"},
                timeout=10,
                headers={"Content-Type": "application/json"}
            )
            elapsed = (time.time() - start) * 1000  # ms
            
            if resp.status_code == 200:
                print(f"   ✅ Response time: {elapsed:.0f}ms")
                if elapsed < 2000:
                    print(f"      Performance: Excellent")
                elif elapsed < 5000:
                    print(f"      Performance: Good")
                else:
                    print(f"      Performance: Acceptable")
                self.log_test("response_time", True, {"ms": elapsed})
                return True
            else:
                print(f"   ❌ Request failed: {resp.status_code}")
                self.log_test("response_time", False)
                return False
        except Exception as e:
            print(f"   ❌ Error: {e}")
            self.log_test("response_time", False)
            return False

    def log_test(self, name, passed, data=None):
        """Log test result"""
        if passed:
            self.results["passed"] += 1
        else:
            self.results["failed"] += 1
        
        self.results["tests"].append({
            "name": name,
            "passed": passed,
            "data": data
        })

    def run_all_tests(self):
        """Run all tests"""
        print("")
        print("╔════════════════════════════════════════════════════════════╗")
        print("║        HDS Vision Daemon Self-Test Suite                  ║")
        print("╚════════════════════════════════════════════════════════════╝")
        print("")
        print(f"🎯 Testing Vision API at {self.api_url}")
        print("")

        tests = [
            self.test_health,
            self.test_capture_screen,
            self.test_analyze_image,
            self.test_element_detection,
            self.test_api_response_time,
        ]

        for test in tests:
            try:
                test()
            except Exception as e:
                print(f"   ❌ Test error: {e}")
            print("")

        # Summary
        print("╔════════════════════════════════════════════════════════════╗")
        print("║                    TEST SUMMARY                            ║")
        print("╚════════════════════════════════════════════════════════════╝")
        print("")
        print(f"✅ Passed: {self.results['passed']}")
        print(f"❌ Failed: {self.results['failed']}")
        total = self.results['passed'] + self.results['failed']
        percentage = (self.results['passed'] / total * 100) if total > 0 else 0
        print(f"📊 Success Rate: {percentage:.0f}%")
        print("")

        if self.results['failed'] == 0:
            print("🎉 All tests passed! Vision daemon is working correctly.")
        else:
            print("⚠️  Some tests failed. Check the logs above.")

        print("")

        # Save results
        results_file = Path("ai-mind/test_results/vision_self_test.json")
        results_file.parent.mkdir(parents=True, exist_ok=True)
        results_file.write_text(json.dumps(self.results, indent=2))
        print(f"📄 Results saved to: {results_file}")

        return self.results['failed'] == 0


def main():
    import argparse
    
    parser = argparse.ArgumentParser(description="HDS Vision Self-Test")
    parser.add_argument('--port', type=int, default=9001, help='Vision daemon port')
    args = parser.parse_args()

    tester = VisionSelfTest(args.port)
    success = tester.run_all_tests()
    exit(0 if success else 1)


if __name__ == "__main__":
    main()
