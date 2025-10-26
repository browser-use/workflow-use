import asyncio
import json
import logging
from datetime import datetime, timedelta

from browser_use import Browser

from workflow_use.workflow.semantic_executor import SemanticWorkflowExecutor

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class TravelBookingDemo:
	"""Demo for complex travel booking UI interactions like Skyscanner."""

	def __init__(self):
		self.browser = None
		self.executor = None
		self.interaction_log = []

	async def setup(self):
		"""Initialize browser and executor."""
		self.browser = Browser()
		await self.browser.start()
		self.executor = SemanticWorkflowExecutor(self.browser)

	async def cleanup(self):
		"""Clean up resources."""
		if self.browser:
			await self.browser.close()

	def log_interaction(self, action: str, element: str, success: bool, details: str = ''):
		"""Log interaction for analysis."""
		self.interaction_log.append(
			{
				'timestamp': datetime.now().isoformat(),
				'action': action,
				'element': element,
				'success': success,
				'details': details,
			}
		)

	async def demo_skyscanner_booking(self):
		"""Demonstrate complex booking flow on Skyscanner."""
		print('🛫 Starting Skyscanner Booking Demo')
		print('=' * 60)

		page = await self.browser.get_current_page()

		try:
			# Navigate to Skyscanner
			await page.goto('https://www.skyscanner.com', timeout=30000)
			await page.wait_for_load_state('networkidle')

			print('✅ Loaded Skyscanner homepage')

			# Step 1: Handle departure city input
			print('\n1️⃣ Setting departure city...')
			departure_input = await self.executor.find_element_with_context('From', ['departure', 'origin'])
			if departure_input:
				await self._interact_with_element(page, departure_input, 'click')
				await page.fill(departure_input['selectors'], 'San Francisco')
				await page.keyboard.press('Escape')  # Close dropdown
				self.log_interaction('input', 'departure_city', True, 'San Francisco')
				print('✅ Set departure city: San Francisco')
			else:
				print('❌ Could not find departure city input')
				return False

			# Step 2: Handle destination city input
			print('\n2️⃣ Setting destination city...')
			destination_input = await self.executor.find_element_with_context('To', ['destination', 'arrival'])
			if destination_input:
				await self._interact_with_element(page, destination_input, 'click')
				await page.fill(destination_input['selectors'], 'New York')
				await page.keyboard.press('Escape')
				self.log_interaction('input', 'destination_city', True, 'New York')
				print('✅ Set destination city: New York')
			else:
				print('❌ Could not find destination city input')
				return False

			# Step 3: Handle departure date selection
			print('\n3️⃣ Selecting departure date...')
			departure_date = (datetime.now() + timedelta(days=30)).strftime('%Y-%m-%d')

			# First click the departure date field to open calendar
			date_field = await self.executor.find_element_with_context('Depart', ['date', 'departure'])
			if not date_field:
				# Try alternative selectors for departure date button
				alternative_selectors = [
					'button[data-testid="depart-btn"]',
					'[data-testid="depart-btn"]',
					'button:has-text("Depart")',
					'button:has-text("Add date")',
					'.depart-date',
					'#depart-date',
				]

				for selector in alternative_selectors:
					try:
						await page.click(selector, timeout=2000)
						date_field = {'found': True, 'selector': selector}
						print(f'✅ Clicked departure button with: {selector}')
						break
					except Exception:
						continue

			if date_field:
				if not date_field.get('found'):
					await self._interact_with_element(page, date_field, 'click')

				await asyncio.sleep(3)  # Wait for calendar to load

				# Refresh semantic mapping to detect calendar elements
				await self.executor._refresh_semantic_mapping()

				# Now try to select the specific date
				calendar_date = await self.executor.select_calendar_date(departure_date, 'departure')
				if calendar_date:
					await self._interact_with_element(page, calendar_date, 'click')
					self.log_interaction('calendar', 'departure_date', True, departure_date)
					print(f'✅ Selected departure date: {departure_date}')
				else:
					print(f'❌ Could not find departure date: {departure_date}')
					# Try fallback approach
					await self._try_calendar_fallback(page, departure_date, 'departure')

			# Step 4: Handle return date selection
			print('\n4️⃣ Selecting return date...')
			return_date = (datetime.now() + timedelta(days=37)).strftime('%Y-%m-%d')

			# Try to select return date
			calendar_date = await self.executor.select_calendar_date(return_date, 'return')
			if calendar_date:
				await self._interact_with_element(page, calendar_date, 'click')
				self.log_interaction('calendar', 'return_date', True, return_date)
				print(f'✅ Selected return date: {return_date}')
			else:
				print(f'❌ Could not find return date: {return_date}')
				await self._try_calendar_fallback(page, return_date, 'return')

			# Step 5: Handle travelers and cabin class
			print('\n5️⃣ Setting travelers and cabin class...')
			travelers_button = await self.executor.find_element_with_context('Travelers', ['passengers', 'cabin'])
			if travelers_button:
				await self._interact_with_element(page, travelers_button, 'click')
				await asyncio.sleep(1)

				# Try to select economy class
				economy_option = await self.executor.select_dropdown_option('Economy', 'cabin class')
				if economy_option:
					await self._interact_with_element(page, economy_option, 'click')
					self.log_interaction('dropdown', 'cabin_class', True, 'Economy')
					print('✅ Selected Economy class')

			# Step 6: Search for flights
			print('\n6️⃣ Searching for flights...')
			search_button = await self.executor.find_element_with_context('Search', ['flights', 'search'])
			if search_button:
				await self._interact_with_element(page, search_button, 'click')

				# Handle dynamic content loading
				loading_success = await self.executor.handle_dynamic_content_loading(search_button, 'results', timeout=15000)

				if loading_success:
					self.log_interaction('search', 'flight_search', True, 'Search completed')
					print('✅ Flight search completed')

					# Step 7: Analyze and select flight
					await self._demo_flight_selection(page)
				else:
					print('⚠️ Flight search may still be loading...')

			return True

		except Exception as e:
			logger.error(f'Demo failed: {e}')
			return False

	async def _demo_flight_selection(self, page):
		"""Demonstrate intelligent flight selection."""
		print('\n7️⃣ Analyzing flight options...')

		# Wait a bit for results to load
		await asyncio.sleep(3)

		# Refresh semantic mapping to get flight results
		await self.executor._refresh_semantic_mapping()

		# Try to find and select a flight based on criteria
		flight_criteria = {'price_range': '200-500', 'time': 'morning', 'airline': 'Southwest'}

		selected_flight = await self.executor.select_flight_option(flight_criteria)
		if selected_flight:
			await self._interact_with_element(page, selected_flight, 'click')
			self.log_interaction('selection', 'flight_option', True, str(flight_criteria))
			print(f'✅ Selected flight based on criteria: {flight_criteria}')
		else:
			# Fallback: try to find any "Select" button or other flight-related elements
			select_buttons = []
			flight_elements = []

			# Look for various flight selection patterns
			for text, element_info in self.executor.current_mapping.items():
				text_lower = text.lower()
				element_type = element_info.get('element_type', '')

				# Look for select buttons
				if 'select' in text_lower and 'button' in element_type:
					select_buttons.append((text, element_info))

				# Look for flight-related elements
				if any(keyword in text_lower for keyword in ['flight', 'book', 'choose', 'view']):
					flight_elements.append((text, element_info))

			if select_buttons:
				# Select the first available flight
				first_flight = select_buttons[0][1]
				await self._interact_with_element(page, first_flight, 'click')
				self.log_interaction('selection', 'flight_option', True, 'First available')
				print('✅ Selected first available flight')
			elif flight_elements:
				# Try flight-related elements
				first_flight = flight_elements[0][1]
				await self._interact_with_element(page, first_flight, 'click')
				self.log_interaction('selection', 'flight_option', True, 'Flight element')
				print(f'✅ Clicked flight element: {flight_elements[0][0]}')
			else:
				print('❌ Could not find any flight selection options')
				# Debug: show what elements are available
				print('   🔍 Available elements:')
				count = 0
				for text, element_info in self.executor.current_mapping.items():
					if count < 10:  # Show first 10 elements
						print(f'      - {text} ({element_info.get("element_type", "unknown")})')
						count += 1
					else:
						print(f'      ... and {len(self.executor.current_mapping) - 10} more')
						break

	async def _interact_with_element(self, page, element_info: dict, action: str):
		"""Safely interact with an element using multiple fallback strategies."""
		selectors = [
			element_info.get('selectors'),
			element_info.get('hierarchical_selector'),
			element_info.get('fallback_selector'),
		]

		for selector in selectors:
			if not selector:
				continue

			try:
				if action == 'click':
					await page.click(selector, timeout=5000)
				elif action == 'fill':
					await page.fill(selector, element_info.get('value', ''))

				logger.info(f'Successfully {action}ed element: {selector}')
				return True

			except Exception as e:
				logger.debug(f'Failed to {action} {selector}: {e}')
				continue

		logger.warning(f'Could not {action} element with any selector')
		return False

	async def _try_calendar_fallback(self, page, date_value: str, calendar_type: str):
		"""Try fallback approaches for calendar date selection."""
		print(f'   🔄 Trying fallback calendar selection for {date_value}')

		try:
			# Parse date to get day number
			from datetime import datetime

			dt = datetime.strptime(date_value, '%Y-%m-%d')
			day = dt.strftime('%d').lstrip('0')  # Remove leading zero
			day_with_zero = dt.strftime('%d')  # Keep leading zero
			month_name = dt.strftime('%B')
			month_short = dt.strftime('%b')

			# Try common calendar day selectors for Skyscanner and other sites
			day_selectors = [
				# Skyscanner specific
				f'[data-testid*="day-{day}"]',
				f'[data-testid*="date-{day}"]',
				f'button[aria-label*="{month_name} {day}"]',
				f'button[aria-label*="{month_short} {day}"]',
				f'[data-date="{date_value}"]',
				f'[data-date*="{day_with_zero}"]',
				# Generic calendar selectors
				f'[role="gridcell"]:has-text("{day}")',
				f'[role="gridcell"][aria-label*="{day}"]',
				f'.calendar-day:has-text("{day}")',
				f'.day:has-text("{day}")',
				f'button:has-text("{day}")',
				f'td:has-text("{day}")',
				f'[aria-label*="{dt.strftime("%B %d")}"]',
				f'[aria-label*="{dt.strftime("%b %d")}"]',
				f'[title*="{dt.strftime("%B %d")}"]',
			]

			# First check if calendar is visible
			calendar_visible = False
			calendar_selectors = [
				'[role="dialog"]',
				'.calendar',
				'.datepicker',
				'[data-testid*="calendar"]',
				'[data-testid*="datepicker"]',
			]

			for cal_selector in calendar_selectors:
				try:
					await page.wait_for_selector(cal_selector, timeout=1000)
					calendar_visible = True
					print(f'   📅 Calendar detected: {cal_selector}')
					break
				except Exception:
					continue

			if not calendar_visible:
				print('   ⚠️ No calendar visible, trying to open it first')
				# Try to click date button again
				date_buttons = [
					'button[data-testid="depart-btn"]',
					'button[data-testid="return-btn"]',
					'button:has-text("Depart")',
					'button:has-text("Return")',
				]

				for btn in date_buttons:
					try:
						await page.click(btn, timeout=1000)
						await asyncio.sleep(2)
						break
					except Exception:
						continue

			# Try to select the date
			for selector in day_selectors:
				try:
					await page.click(selector, timeout=2000)
					print(f'   ✅ Fallback success with: {selector}')
					self.log_interaction('calendar_fallback', f'{calendar_type}_date', True, date_value)
					return True
				except Exception as e:
					logger.debug(f'   Failed selector {selector}: {e}')
					continue

			print(f'   ❌ All fallback attempts failed for {date_value}')
			self.log_interaction('calendar_fallback', f'{calendar_type}_date', False, date_value)
			return False

		except Exception as e:
			logger.error(f'Calendar fallback error: {e}')
			return False

	def generate_interaction_report(self):
		"""Generate a comprehensive interaction report."""
		report = {
			'metadata': {
				'generated_at': datetime.now().isoformat(),
				'total_interactions': len(self.interaction_log),
				'demo_type': 'travel_booking',
			},
			'interaction_summary': {},
			'success_rates': {},
			'detailed_log': self.interaction_log,
		}

		# Calculate success rates by action type
		action_stats = {}
		for interaction in self.interaction_log:
			action = interaction['action']
			if action not in action_stats:
				action_stats[action] = {'total': 0, 'success': 0}

			action_stats[action]['total'] += 1
			if interaction['success']:
				action_stats[action]['success'] += 1

		for action, stats in action_stats.items():
			success_rate = (stats['success'] / stats['total']) * 100
			report['success_rates'][action] = f'{success_rate:.1f}%'

		# Save report
		report_file = f'travel_booking_report_{datetime.now().strftime("%Y%m%d_%H%M%S")}.json'
		with open(report_file, 'w') as f:
			json.dump(report, f, indent=2)

		return report_file


async def main():
	"""Main demo function."""
	demo = TravelBookingDemo()

	try:
		await demo.setup()

		print('🚀 Travel Booking UI Demo')
		print('=' * 60)
		print('This demo shows how to handle complex travel booking UIs')
		print('with calendars, dropdowns, and dynamic content.')
		print()

		success = await demo.demo_skyscanner_booking()

		# Generate report
		if demo.interaction_log:
			report_file = demo.generate_interaction_report()
			print(f'\n📄 Generated interaction report: {report_file}')

			# Show summary
			print('\n📊 Interaction Summary:')
			action_counts = {}
			for interaction in demo.interaction_log:
				action = interaction['action']
				action_counts[action] = action_counts.get(action, 0) + 1

			for action, count in action_counts.items():
				success_count = sum(1 for i in demo.interaction_log if i['action'] == action and i['success'])
				print(f'   {action}: {success_count}/{count} successful')

		if success:
			print('\n✅ Demo completed successfully!')
		else:
			print('\n⚠️ Demo completed with some issues')

		input('\nPress Enter to close browser...')

	except KeyboardInterrupt:
		print('\n👋 Demo interrupted by user')
	except Exception as e:
		print(f'\n❌ Demo failed: {e}')
		import traceback

		traceback.print_exc()
	finally:
		await demo.cleanup()


if __name__ == '__main__':
	asyncio.run(main())
