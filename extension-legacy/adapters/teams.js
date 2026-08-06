// Microsoft Teams DOM Layout Helper & Adapter
(function() {
  console.log("Speech Translator MS Teams Adapter loaded.");

  // Observe MS Teams meeting status (detect if user is in an active call)
  const observer = new MutationObserver(() => {
    const meetingStage = document.querySelector('[data-tid="calling-stage"]') || document.querySelector('.ts-calling-screen');
    if (meetingStage) {
      // Teams Meeting is Active
      const badge = document.getElementById("st-platform-badge");
      if (badge) badge.innerText = "MS Teams (Active)";
    }
  });

  observer.observe(document.body, { childList: true, subtree: true });
})();
