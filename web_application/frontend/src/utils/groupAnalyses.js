export const groupAnalyses = (analysesList) => {
  const groups = {};
  const others = [];

  analysesList.forEach(a => {
    if (a.road_path || a.face_path) {
      const key = `${a.road_path || ''}|${a.face_path || ''}`;
      if (!groups[key]) groups[key] = [];
      groups[key].push(a);
    } else {
      others.push([a]);
    }
  });

  const grouped = Object.values(groups).map(group => {
    group.sort((a, b) => new Date(b.created_at) - new Date(a.created_at));
    return group;
  });

  return [...grouped, ...others].sort((a, b) => new Date(b[0].created_at) - new Date(a[0].created_at));
};
