// frontend/tests/run_tests.js
//
// Minimal test runner - discovers and runs every test_*.js file in this
// directory. No framework dependency, consistent with the no-build-step
// nature of this frontend. Mirrors pytest's auto-discovery on the backend
// side, at Node-script scale.
//
// Run with: node frontend/tests/run_tests.js

const fs = require('fs');
const path = require('path');

async function main() {
  const testDir = __dirname;
  const files = fs.readdirSync(testDir)
    .filter(f => f.startsWith('test_') && f.endsWith('.js'))
    .sort();

  if (files.length === 0) {
    console.log('No test files found (expected test_*.js in frontend/tests/)');
    process.exit(1);
  }

  console.log(`Running ${files.length} frontend test file(s):\n`);

  let anyFailed = false;
  for (const file of files) {
    console.log(`── ${file} ──`);
    const fullPath = path.join(testDir, file);

    // Each test file is a standalone script that exits non-zero on failure.
    // Run it as a child process so one file's crash doesn't take down the rest.
    const { execFileSync } = require('child_process');
    try {
      const output = execFileSync(process.execPath, [fullPath], { encoding: 'utf8' });
      process.stdout.write(output);
    } catch (err) {
      if (err.stdout) process.stdout.write(err.stdout);
      if (err.stderr) process.stderr.write(err.stderr);
      anyFailed = true;
    }
    console.log('');
  }

  if (anyFailed) {
    console.error('❌ One or more frontend test files failed');
    process.exit(1);
  } else {
    console.log('✅ All frontend tests passed');
  }
}

main();