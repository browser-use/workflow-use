from browser_use.llm import ChatBrowserUse

from workflow_use.mcp.service import get_mcp_server

# async def main():
if __name__ == '__main__':
	llm_instance = ChatBrowserUse(model='bu-latest')

	print('[FastMCP Server] Starting MCP server...')
	# This will run the FastMCP server, typically using stdio transport by default.
	# For CLI execution like `fastmcp run workflow_use.mcp.server:mcp_app`,
	# this __main__ block might be bypassed by FastMCP's runner,
	# but it's good practice for direct Python execution.
	mcp = get_mcp_server(llm_instance, workflow_dir='./tmp')
	mcp.run(
		transport='sse',
		host='0.0.0.0',
		port=8008,
	)

	# async with Client(mcp) as client:
	# 	tools = await client.list_tools()
	# 	print(f'Available tools: {tools}')

	# 	result = await client.call_tool(
	# 		'Government_Form_Submission_1.0',
	# 		{
	# 			'first_name': 'John',
	# 			'last_name': 'Smith',
	# 			'social_security_last4': '1234',
	# 			'gender': 'male',
	# 			'marital_status': 'single',
	# 		},
	# 	)

	# 	print(result)


# if __name__ == '__main__':
# 	asyncio.run(main())
