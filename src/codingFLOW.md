**coding**

user feedback tool

```

# User feedback tool
class UserFeedbackTool:
    def __init__(self, prompt: str):
        self.prompt = prompt

    def request_feedback(self, context: str) -> str:
        print(f"\nUser Feedback Required:\n{self.prompt}\n\nContext:\n{context}\n")
        while True:
            feedback = input("Please provide your feedback (or type 'done' if satisfied): ")
            if feedback.lower() == "done":
                break
            print(f"\nUser Feedback: {feedback}\n")
        return feedback
```

```
def mainflow():
    # resources for the agents, roles, goals, tools, verbose, persona, etc.
    text_doc1 = "inputs/problem_description.txt"
    text_doc2 = "inputs/sample_solutions.txt"

    # define toolsettings for flow sesh
    problem_reader_tool = TextReaderTool(text_doc1, chunk_size=1000, num_chunks=1)
    solution_reader_tool = TextReaderTool(text_doc2, chunk_size=1000, num_chunks=5)

    # create agents
    pseudocode_generator = Agent(
        role='Pseudocode Generator',
        goal='Generate pseudocode based on the problem description.',
        persona='''
You are a world-class competitive programmer.
Please reply with a Python 3 solution to the problem below. 
First, reason through the problem and conceptualize a solution.
Then write detailed pseudocode to uncover any potential logical errors or omissions.
Finally output the working Python code for your solution, ensuring to fix any errors uncovered while writing pseudocode.

No outside libraries are allowed.''',
        tools={"problem_reader": problem_reader_tool},
        verbose=True
    )

    reflective_analyzer = Agent(
        role='Reflective Analyzer',
        goal='Analyze the generated pseudocode and provide reflective feedback.',
        persona="You are a meticulous code reviewer with a keen eye for potential issues and improvements.",
        verbose=True
    )

    debugger = Agent(
        role='Debugger',
        goal='Debug and refine the pseudocode based on the reflective analysis.',
        persona="You are a seasoned debugger skilled at identifying and fixing issues in pseudocode.",
        tools={"solution_reader": solution_reader_tool},
        verbose=True
    )
    # Create the UserFeedbackTool instance
    user_feedback_tool = UserFeedbackTool(prompt="Please review the generated output and provide feedback for improvement.")

    # Create the Reviewer agent
    reviewer_agent = Agent(
        role='Reviewer',
        goal='Review the generated output and provide feedback for improvement.',
        persona="You are an experienced reviewer with expertise in providing constructive feedback.",
        tools={"user_feedback": user_feedback_tool},
        verbose=True
    )
    # create tasks
    generate_output_task = Task(
        instructions="Generate the desired output based on the given inputs.",
        expected_output="The generated output that needs to be reviewed.",
        agent=pseudocode_generator,  # Replace with the appropriate agent
        context=[],  # Add any necessary context tasks
        tool_name="problem_reader",  # Replace with the appropriate tool name
    )
    # Create the review_output_task
    review_output_task = Task(
        instructions="Review the generated output and provide feedback for improvement.",
        expected_output="Constructive feedback and suggestions for enhancing the output.",
        agent=reviewer_agent,
        context=[generate_output_task],
        tool_name="user_feedback",
    )


    generate_pseudocode_task = Task(
        instructions="Read the problem description and generate pseudocode for a solution.",
        expected_output="Well-structured pseudocode that outlines a solution to the problem.",
        agent=pseudocode_generator,
        tool_name="problem_reader",
    )

    analyze_pseudocode_task = Task(
        instructions="Analyze the generated pseudocode and provide reflective feedback.",
        expected_output="Reflective feedback highlighting potential issues and areas for improvement.",
        agent=reflective_analyzer,
        context=[generate_pseudocode_task],
    )

    debug_pseudocode_task = Task(
        instructions="Debug and refine the pseudocode based on the reflective analysis.",
        expected_output="Refined pseudocode that addresses the identified issues and incorporates improvements.",
        agent=debugger,
        context=[analyze_pseudocode_task],
        tool_name="solution_reader",
    )

    # create the squad and define the flow
    squad = Squad(
        agents=[pseudocode_generator, reflective_analyzer, debugger, reviewer_agent],
        tasks=[generate_output_task, review_output_task, generate_pseudocode_task, analyze_pseudocode_task, debug_pseudocode_task],
        verbose=True,
        log_file="squad_flow_" + datetime.now().strftime("%Y%m%d%H%M%S") + ".json"
    )
```
