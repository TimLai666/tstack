# Tool and API discoverability

When designing or changing our CLI tools, MCP tools, or APIs, put their supported operations and usage in the interface itself.

- **CLI:** Provide an overview listing all supported commands. A bare invocation should show the overview when it has no existing operation to perform. Always implement `--help`, with parameters, required values, defaults, examples, and errors documented in each command's help. A single-operation script can use its top-level help for both overview and details.
- **API:** Provide an overview endpoint listing all supported public endpoints and their methods, with links to each operation's usage. Use the API base path when available; preserve an existing base operation by linking to a dedicated overview instead. Publish OpenAPI JSON covering parameters, request and response schemas, authentication, and errors. Each operation's documentation must be discoverable from the overview.
- **MCP:** Document each operation in its registered tool description and input schema, including usage constraints and return behavior. Tool registration supplies discovery, so a separate overview tool is not required.
- **Skills:** Explain tool selection, workflow, and decision-relevant constraints. Point to the tool's overview, help, registered schema, or OpenAPI document instead of duplicating its complete command and parameter manual in a skill or its references.
- **Updates:** Change the overview, command help, operation descriptions, and OpenAPI JSON together with the affected functionality. Prefer generating them from the implementation's command or route definitions. Verify that every supported operation is discoverable and that documented examples, parameters, and responses match actual behavior before delivery.
