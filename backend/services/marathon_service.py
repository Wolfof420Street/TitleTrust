import logging
from services.firebase import db
from agent.marathon_loop import MarathonLoop, AgentState

logger = logging.getLogger("MarathonService")

def run_marathon_task(session_id: str, file_path: str = None):
    """
    Entry point for the Background Task (Cloud Task).
    """
    logger.info(f"🏃 Starting Marathon Task: {session_id}")
    
    agent = MarathonLoop(db, session_id)
    
    # If first run, initialize memory with the file path
    state = agent.load_state()
    if state.memory == [] and file_path:
        state.memory.append(f"Received initial file: {file_path}")
        state.image_path = file_path  # Critical: Set image path for analysis
        state.status = AgentState.RUNNING
        agent.save_state(state)
        
        # Note: 'Audit Started' notification checks are handled by Frontend listening to status change 
        # or we could add explicit start notification in Loop if preferred.

    # Run the Loop Steps
    # In a real Cloud Task, we might run one step or a few until "SLEEP"
    agent.run_step()
    
    # Check status after run
    final_state = agent.load_state()
    if final_state.status == AgentState.SLEEPING:
         logger.info(f"💤 Agent went to sleep. Task ending.")
