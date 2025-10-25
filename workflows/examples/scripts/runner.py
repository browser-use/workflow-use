import asyncio

from browser_use.llm import ChatOpenAI

from workflow_use.workflow.service import Workflow

llm = ChatOpenAI(model='gpt-4.1-mini')


async def main():
	workflow = Workflow.load_from_file('examples/example.workflow.json', llm)
	print(workflow)

	first_name = 'John'
	last_name = 'Doe'
	social_security_last4 = '1234'

	await workflow.run(
		inputs={'first_name': first_name, 'last_name': last_name, 'social_security_last4': social_security_last4},
		close_browser_at_end=False,
	)


if __name__ == '__main__':
	asyncio.run(main())
